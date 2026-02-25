import logging
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy, merge_informative_pair
from pandas import DataFrame
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AMRS_v13_ExtractorStrategy(IStrategy):
    """
    AMRS v13 - 利潤萃取者模式
    優化重點：
    1. 延續 V12 高品質進場 (Volume 2.5x, RSI > 35, Macro ADX > 25)
    2. 優化追蹤止損 (0.8% 觸發)，更早鎖定利潤。
    3. 加入 ATR 動態止盈與持倉保護期，減少手續費損耗。
    """
    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 120

    # --- 交易性能參數 ---
    # 稍微放寬 ROI，讓 Custom Exit 與 Trailing Stop 主導離場
    minimal_roi = {
        "0": 0.20,  # 20% 硬性止盈
        "360": 0.05,  # 6小時後 5% 止盈
        "1440": 0.015  # 24小時後 1.5% 止盈 (確保高於手續費)
    }

    # 止損維持在 3%，給予波動空間但保護本金
    stoploss = -0.03

    # 追蹤止損：鎖定 0.8% 以上的利潤
    trailing_stop = True
    trailing_stop_positive = 0.001
    trailing_stop_positive_offset = 0.008  # 獲利達 0.8% 開啟 (原 1.5%)
    trailing_only_offset_is_reached = True

    def informative_pairs(self):
        return [(self.config['stake_currency'], '1d')]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 1. 日線指標 (1D) ---
        informative = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='1d')
        informative['ma25_day'] = ta.SMA(informative, timeperiod=25)
        informative['day_slope'] = informative['ma25_day'].diff(3)
        informative['adx'] = ta.ADX(informative)
        informative['minus_di'] = ta.MINUS_DI(informative)
        informative['plus_di'] = ta.PLUS_DI(informative)

        dataframe = merge_informative_pair(dataframe, informative, self.timeframe, '1d', ffill=True)

        # --- 2. 短線指標 (15m) ---
        dataframe['ma7'] = ta.SMA(dataframe, timeperiod=7)
        dataframe['ma25'] = ta.SMA(dataframe, timeperiod=25)
        dataframe['ma99'] = ta.SMA(dataframe, timeperiod=99)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        # 乖離率與成交量
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=30).mean()

        # 離場確認邏輯 (MA7 確認)
        dataframe['ma7_cross_above'] = (dataframe['close'] > dataframe['ma7']).astype(int)
        dataframe['streak_ma7'] = dataframe['ma7_cross_above'].rolling(window=5).sum()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        進場邏輯：沿用 V12 高品質進場
        """
        # 1. 強度過濾：日線強勢趨勢
        macro_trend = (
                (dataframe['day_slope_1d'] < 0) &
                (dataframe['adx_1d'] > 25) &
                (dataframe['minus_di_1d'] > dataframe['plus_di_1d'])
        )

        # 2. 爆量條件：2.5 倍平均成交量
        volume_spike = (dataframe['volume'] > dataframe['volume_mean'] * 2.5)

        # 3. 空間過濾：RSI > 35 避開底部追空
        space_filter = (dataframe['rsi'] > 35)

        # 4. 價格結構
        price_structure = (
                (dataframe['close'] < dataframe['ma99']) &
                (dataframe['close'] < dataframe['ma25'])
        )

        dataframe.loc[
            macro_trend & volume_spike & space_filter & price_structure,
            ["enter_short", "enter_tag"]
        ] = (1, "v13_sniper_entry")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 技術指標離場：MA7 站穩
        dataframe.loc[
            (dataframe["streak_ma7"] >= 5),
            "exit_short"
        ] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        """
        自定義離場邏輯：動態鎖定利潤與摩擦保護
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]

        # 計算持倉分鐘數
        trade_duration = (current_time - trade.open_date_utc).total_seconds() / 60

        # --- 邏輯 A: ATR 動態爆發止盈 ---
        # 如果當前獲利超過 3 倍 ATR 的波動率，代表出現超跌噴發，直接落袋為安
        atr_threshold = (last_candle['atr'] / current_rate) * 3.0
        if current_profit > atr_threshold and current_profit > 0.01:
            return "v13_atr_profit_burst"

        # --- 邏輯 B: 持倉保護期 (抗洗盤) ---
        # 前 60 分鐘內，除非獲利 > 0.8% 或 虧損 > 2%，否則不允許因為 MA7 指標離場
        if trade_duration < 60:
            if 0.008 > current_profit > -0.02:
                return None

        # --- 邏輯 C: 摩擦成本牆 (保護平均獲利) ---
        # 如果利潤低於 0.3%，且持倉時間未超過 3 小時，避免過早因噪音離場
        if current_profit < 0.003 and trade_duration < 180:
            return None

        # 快速利潤鎖定
        if current_profit > 0.03:
            return "v13_quick_profit_lock"

        return None
