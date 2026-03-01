import logging
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import numpy as np

logger = logging.getLogger(__name__)


class AMRS4_1_1Strategy_v2(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 120

    # --- 實戰參數控制 ---
    minimal_roi = {"0": 10.0}  # 停用 ROI，交給 Custom Exit
    stoploss = -0.05  # 實戰建議設為 5%，保護極端行情

    # 均線與過濾參數
    ma7_len, ma25_len, ma99_len = 7, 25, 99
    lookback_candles = 10
    exit_confirm_candles = 3

    # ATR 與 RSI 閾值
    atr_multiplier = 1.5  # 實體必須大於 1.5 倍 ATR
    rsi_oversold = 25  # RSI 低於 25 不進場做空

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. 基礎均線與斜率
        dataframe["ma7"] = ta.SMA(dataframe, timeperiod=self.ma7_len)
        dataframe["ma25"] = ta.SMA(dataframe, timeperiod=self.ma25_len)
        dataframe["ma99"] = ta.SMA(dataframe, timeperiod=self.ma99_len)
        dataframe["ma7_slope"] = dataframe["ma7"].diff()
        dataframe["ma25_slope"] = dataframe["ma25"].diff()

        # 2. 波動率 (ATR) 與 RSI
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # 3. 前 10 根實體最低位
        dataframe['body_min'] = np.minimum(dataframe['open'], dataframe['close'])
        dataframe['ten_candle_low'] = dataframe['body_min'].shift(1).rolling(window=self.lookback_candles).min()

        # 4. 當前 K 棒實體大小
        dataframe['body_size'] = dataframe['open'] - dataframe['close']

        # 5. 連續收盤高於 MA7 計數
        dataframe["close_gt_ma7"] = dataframe["close"] > dataframe["ma7"]
        dataframe["streak_ma7"] = self._streak_true(dataframe["close_gt_ma7"])

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 【優化後的進場濾網】
        # - 加入 RSI > 25 (避免在超賣區空在最低點)
        # - 加入 body_size > atr * 1.5 (確保爆發力)
        entry_filter = (
                (dataframe["close"] < dataframe["ma99"]) &
                (dataframe["ma7"] < dataframe["ma25"]) &
                (dataframe["ma7_slope"] < 0) &
                (dataframe["ma25_slope"] < 0) &
                (dataframe["close"] < dataframe["ten_candle_low"]) &
                (dataframe["rsi"] > self.rsi_oversold) &
                (dataframe["body_size"] >= (dataframe['atr'] * self.atr_multiplier))
        )

        dataframe.loc[entry_filter, "enter_short"] = 1
        dataframe.loc[entry_filter, "enter_tag"] = "pro_breakout"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 常規出場：連續 3 根 K 棒站上 MA7
        dataframe.loc[dataframe["streak_ma7"] >= self.exit_confirm_candles, "exit_short"] = 1
        dataframe.loc[dataframe["streak_ma7"] >= self.exit_confirm_candles, "exit_tag"] = "signal_ma7_streak"

        # 硬止損：收盤站上 MA25
        dataframe.loc[dataframe["close"] > dataframe["ma25"], "exit_short"] = 1
        dataframe.loc[dataframe["close"] > dataframe["ma25"], "exit_tag"] = "signal_ma25_hard"

        return dataframe

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        # 【優化：獲利保護機制】
        # 當利潤超過 1.2% 時，只要「1 根」收盤站上 MA7 就立即止盈 (敏捷出場)
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        if current_profit > 0.012:
            if last_candle['close'] > last_candle['ma7']:
                return "profit_protection_exit"

        return None

    @staticmethod
    def _streak_true(cond: pd.Series) -> pd.Series:
        cond = cond.fillna(False).astype(bool)
        grp = (~cond).cumsum()
        return cond.groupby(grp).cumsum().astype(int)