import logging
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import numpy as np

logger = logging.getLogger(__name__)


class AMRS_v23_TrendCatcherShort(IStrategy):
    """
    AMRS v23 - 趨勢捕捉者 (空頭優化版)
    優化方向：
    1. 增加交易樣本：放寬硬性 ATR 與 Volume 限制。
    2. 延長持倉時間：移除敏感的 ema_slope 離場，改用 RSI 超賣反彈離場。
    3. 動態風險控制：調整階梯止損，讓利潤有空間成長。
    """
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 120

    # 物理止損放寬，交給 custom_stoploss 處理精細化操作
    stoploss = -0.04
    minimal_roi = {
        "0": 0.15,  # 提高目標利潤，不輕易獲利了結
        "240": 0.05,  # 4小時後
        "720": 0.02,  # 12小時後
        "1440": 0.01  # 24小時後保本離場
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 基礎指標
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_pct'] = (dataframe['atr'] / dataframe['close']) * 100

        # 移動平均線
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)

        # 相對波動率：當前波動是否高於近期平均
        dataframe['volatility_avg'] = dataframe['atr_pct'].rolling(window=30).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # 1. 趨勢過濾：大趨勢向下
                    (dataframe['close'] < dataframe['ema_200']) &
                    (dataframe['ema_fast'] < dataframe['ema_slow']) &

                    # 2. 相對波動率：只要當前波動不低於平均的 80% 即可 (放寬)
                    (dataframe['atr_pct'] > dataframe['volatility_avg'] * 0.8) &

                    # 3. RSI 高位勾頭：做空的核心點
                    (dataframe['rsi'] > 50) &
                    (dataframe['rsi'] < dataframe['rsi'].shift(1)) &

                    # 4. 成交量：只要有溫和放量即可 (1.1x)
                    (dataframe['volume'] > dataframe['volume'].rolling(20).mean() * 1.1)
            ),
            'enter_short'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # 改進：只有在 RSI 從超賣區(<30) 向上反彈超過 35 時，才認為下跌動能暫時消失
                    (dataframe['rsi'] > 35) &
                    (dataframe['rsi'].shift(1) < 30) &
                    (dataframe['close'] > dataframe['ema_fast'])
            ),
            'exit_short'
        ] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        優化階梯止損：在 1% 利潤前不做激進保護，防止被掃出場
        """
        # 1. 獲利 > 2.5%：大幅鎖利
        if current_profit >= 0.025:
            return 0.01

        # 2. 獲利 > 1.2%：保本並鎖定 0.5%
        if 0.012 <= current_profit < 0.025:
            return 0.005

        # 3. 獲利 > 0.6%：啟動微利保護 (移至 0.1%)
        if 0.006 <= current_profit < 0.012:
            return 0.001

        # 4. 超時保護：持倉超過 8 小時且無利潤，縮減止損至 1.5%
        trade_duration = (current_time - trade.open_date_utc).total_seconds() / 3600
        if trade_duration > 8 and current_profit < 0:
            return -0.015

        return self.stoploss