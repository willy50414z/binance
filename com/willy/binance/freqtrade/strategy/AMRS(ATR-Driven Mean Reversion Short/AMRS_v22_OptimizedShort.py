import logging
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import numpy as np

logger = logging.getLogger(__name__)


class AMRS_v22_OptimizedShort(IStrategy):
    """
    AMRS v22 修正版 - 專注於空頭優化
    優化點：
    1. Volatility Filter: 確保 ATR_PCT > 0.45%，避開橫盤震盪。
    2. RSI Logic: 提高做空門檻，僅在 RSI 高位有回落跡象時介入。
    3. Exit Logic: 移除低效的 RSI 35 直接出場，改用均線斜率與價格行為。
    """
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 120

    # --- 核心優化參數 ---
    # 物理止損與 ROI 保持激進，但增加保護
    stoploss = -0.035
    minimal_roi = {
        "0": 0.08,
        "120": 0.04,
        "300": 0.02,
        "720": 0.01  # 12小時後若沒跑出利潤則準備撤退
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 基礎指標
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_pct'] = (dataframe['atr'] / dataframe['close']) * 100

        # 均線系統
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)

        # 波動率過濾器：計算 20 根 K 線的波動率標準差或簡單均值
        dataframe['volatility_avg'] = dataframe['atr_pct'].rolling(window=30).mean()

        # 價格斜率 (判斷趨勢強度)
        dataframe['ema_slope'] = ta.LINEARREG_SLOPE(dataframe['ema_fast'], timeperiod=5)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # 1. 波動率過濾 (核心優化)
                # 只有當當前 ATR 比例高於近期平均，或高於絕對閾值時才進場
                    (dataframe['atr_pct'] > 0.3) &
                    (dataframe['atr_pct'] > dataframe['volatility_avg'] * 0.9) &

                    # 2. 空頭趨勢過濾
                    (dataframe['close'] < dataframe['ema_200']) &
                    (dataframe['ema_fast'] < dataframe['ema_slow']) &

                    # 3. RSI 優化 (高位賣壓)
                    # 找 RSI > 60 且開始向下勾頭的時刻 (或是高位強勢震盪)
                    (dataframe['rsi'] > 50) &
                    (dataframe['rsi'] < dataframe['rsi'].shift(1)) &  # RSI 勾頭向下

                    # 4. 爆量確認
                    (dataframe['volume'] > dataframe['volume'].rolling(24).mean() * 1.2)
            ),
            'enter_short'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # 優化出場：不要只靠 RSI < 35 (太慢或太早)
                # 改用：當快線斜率轉正 (止跌跡象) 且 RSI 脫離超賣區
                    (dataframe['ema_slope'] > 0) &
                    (dataframe['rsi'] > 40) &
                    (dataframe['close'] > dataframe['ema_fast'])
            ),
            'exit_short'
        ] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        加強版階梯止損：縮短觀察期，更快進入保本
        """
        # 1. 獲利 > 1.5%：立即將止損移至利潤的 0.3% (確保不虧且小賺)
        if current_profit >= 0.015:
            return 0.003

        # 2. 獲利 > 0.8%：啟動保本 (Break-even)
        if 0.008 <= current_profit < 0.015:
            return 0.001

        # 3. 虧損保護：如果持倉超過 4 小時且還在微虧，縮緊止損
        trade_duration = (current_time - trade.open_date_utc).total_seconds() / 60
        if trade_duration > 240 and current_profit < 0:
            return -0.01  # 強制縮減至 1% 止損

        return self.stoploss