import logging
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy, DecimalParameter
from pandas import DataFrame
import numpy as np

logger = logging.getLogger(__name__)

class AMRS4_1Strategy_Final(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 120

    # --- 實盤保護機制 ---
    minimal_roi = {"0": 10.0}  # 關閉固定止盈，交給訊號與移動止盈
    stoploss = -0.03           # 3% 原始止損（實盤建議縮小，保護本金）

    # 移動止盈設定
    trailing_stop = True
    trailing_stop_positive = 0.005          # 獲利多少後觸發移動止損
    trailing_stop_positive_offset = 0.015   # 至少獲利 1.5% 才啟動移動
    trailing_only_offset_is_reached = True  # 只有達到 offset 才啟動

    # 策略參數
    ma7_len = 7
    ma25_len = 25
    ma99_len = 99
    exit_confirm_candles = 3
    lookback_candles = 10
    ma7_touch_tolerance = 0.999

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. 均線與斜率
        dataframe["ma7"] = ta.SMA(dataframe, timeperiod=self.ma7_len)
        dataframe["ma25"] = ta.SMA(dataframe, timeperiod=self.ma25_len)
        dataframe["ma99"] = ta.SMA(dataframe, timeperiod=self.ma99_len)
        dataframe["ma7_slope"] = dataframe["ma7"].diff()
        dataframe["ma25_slope"] = dataframe["ma25"].diff()

        # 2. 前 10 根實體最低位
        dataframe['body_min'] = np.minimum(dataframe['open'], dataframe['close'])
        dataframe['ten_candle_low'] = dataframe['body_min'].shift(1).rolling(window=self.lookback_candles).min()

        # 3. 自適應實體長度 (0.5% 的當前價格)
        dataframe['dynamic_min_body'] = dataframe['close'] * 0.005
        dataframe['body_size'] = dataframe['open'] - dataframe['close']

        # 4. 輔助判斷
        dataframe["close_gt_ma7"] = dataframe["close"] > dataframe["ma7"]
        dataframe["consecutive_closes_above_ma7"] = self._streak_true(dataframe["close_gt_ma7"])
        dataframe["prev_high"] = dataframe["high"].shift(1)
        dataframe["signal2_prev_touch"] = (dataframe["prev_high"] >= dataframe["ma7"].shift(1) * self.ma7_touch_tolerance)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_short"] = 0

        # 核心趨勢與破底濾網
        strict_short_filter = (
            (dataframe["close"] < dataframe["ma99"]) &
            (dataframe["ma7"] < dataframe["ma25"]) &
            (dataframe["ma7_slope"] < 0) &
            (dataframe["ma25_slope"] < 0) &
            (dataframe["close"] < dataframe["ten_candle_low"]) &
            (dataframe["body_size"] >= dataframe["dynamic_min_body"]) # 自適應長黑K
        )

        signal1 = strict_short_filter & (dataframe["close"] < dataframe["ma7"]) & (dataframe["close"].shift(1) >= dataframe["ma7"].shift(1))
        signal2 = strict_short_filter & (dataframe["close"] < dataframe["ma7"]) & dataframe["signal2_prev_touch"]

        dataframe.loc[signal1, "enter_short"] = 1
        dataframe.loc[signal1, "enter_tag"] = "s1_breakout"
        dataframe.loc[signal2, "enter_short"] = 1
        dataframe.loc[signal2, "enter_tag"] = "s2_rebound"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_short"] = 0
        signal3 = dataframe["consecutive_closes_above_ma7"] >= self.exit_confirm_candles
        signal4 = dataframe["close"] > dataframe["ma25"]

        dataframe.loc[signal3, "exit_short"] = 1
        dataframe.loc[signal3, "exit_tag"] = "signal3_ma7"
        dataframe.loc[signal4, "exit_short"] = 1
        dataframe.loc[signal4, "exit_tag"] = "signal4_ma25"

        return dataframe

    @staticmethod
    def _streak_true(cond: pd.Series) -> pd.Series:
        cond = cond.fillna(False).astype(bool)
        grp = (~cond).cumsum()
        return cond.groupby(grp).cumsum().astype(int)