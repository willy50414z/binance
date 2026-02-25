import logging
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import numpy as np

logger = logging.getLogger(__name__)


class AMRS4_1Strategy_v2(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 120

    # --- 交易行為控制 ---
    minimal_roi = {"0": 10.0}
    stoploss = -0.25

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    # 均線長度參數
    ma7_len = 7
    ma25_len = 25
    ma99_len = 99

    # 出場與過濾參數
    exit_confirm_candles = 3
    lookback_candles = 10
    min_candle_body = 400  # 實體棒最小點數要求
    ma7_touch_tolerance = 0.999

    @staticmethod
    def _streak_true(cond: pd.Series) -> pd.Series:
        cond = cond.fillna(False).astype(bool)
        grp = (~cond).cumsum()
        return cond.groupby(grp).cumsum().astype(int)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. 計算均線
        dataframe["ma7"] = ta.SMA(dataframe, timeperiod=self.ma7_len)
        dataframe["ma25"] = ta.SMA(dataframe, timeperiod=self.ma25_len)
        dataframe["ma99"] = ta.SMA(dataframe, timeperiod=self.ma99_len)

        # 2. 計算斜率
        dataframe["ma7_slope"] = dataframe["ma7"].diff()
        dataframe["ma25_slope"] = dataframe["ma25"].diff()

        # 3. 前10根K棒實體最低值
        dataframe['body_min'] = np.minimum(dataframe['open'], dataframe['close'])
        dataframe['ten_candle_low'] = dataframe['body_min'].shift(1).rolling(window=self.lookback_candles).min()

        # 4. 當前 K 棒實體大小 (Open - Close)
        dataframe['body_size'] = dataframe['open'] - dataframe['close']

        # 5. Signal 2 輔助判斷
        dataframe["prev_high"] = dataframe["high"].shift(1)
        dataframe["prev_close"] = dataframe["close"].shift(1)
        dataframe["signal2_prev_touch_ma7"] = dataframe["prev_high"] >= (
                    dataframe["ma7"].shift(1) * self.ma7_touch_tolerance)
        dataframe["signal2_prev_close_below_ma7"] = dataframe["prev_close"] < dataframe["ma7"].shift(1)

        # 6. Signal 3 輔助判斷
        dataframe["close_gt_ma7"] = dataframe["close"] > dataframe["ma7"]
        dataframe["consecutive_closes_above_ma7"] = self._streak_true(dataframe["close_gt_ma7"])

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_short"] = 0

        # 【核心過濾條件】
        # 1. 基本趨勢：Price < MA99, MA7 < MA25, Slopes < 0
        # 2. 動能破底：Close < 前10根實體最低點
        # 3. 長黑K確認：實體(Open-Close) > 400 點
        strict_short_filter = (
                (dataframe["close"] < dataframe["ma99"]) &
                (dataframe["ma7"] < dataframe["ma25"]) &
                (dataframe["ma7_slope"] < 0) &
                (dataframe["ma25_slope"] < 0) &
                (dataframe["close"] < dataframe["ten_candle_low"]) &
                (dataframe["body_size"] >= self.min_candle_body) &  # 新增：長黑K條件
                (dataframe["volume"] > 0)
        )

        # Signal 1: 剛由上往下跌破 MA7 且符合長黑K
        signal1 = (
                strict_short_filter &
                (dataframe["close"] < dataframe["ma7"]) &
                (dataframe["close"].shift(1) >= dataframe["ma7"].shift(1))
        )

        # Signal 2: 反彈至 MA7 附近失敗且以長黑K殺出
        signal2 = (
                strict_short_filter &
                (dataframe["close"] < dataframe["ma7"]) &
                dataframe["signal2_prev_touch_ma7"] &
                dataframe["signal2_prev_close_below_ma7"]
        )

        dataframe.loc[signal1, "enter_short"] = 1
        dataframe.loc[signal1, "enter_tag"] = "s1_long_bear_breakout"

        dataframe.loc[signal2, "enter_short"] = 1
        dataframe.loc[signal2, "enter_tag"] = "s2_long_bear_rebound"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_short"] = 0

        # Signal 3: 連續 3 根站上 MA7
        signal3 = dataframe["consecutive_closes_above_ma7"] >= self.exit_confirm_candles

        # Signal 4: 強制止損，站上 MA25
        signal4 = dataframe["close"] > dataframe["ma25"]

        dataframe.loc[signal3, "exit_short"] = 1
        dataframe.loc[signal3, "exit_tag"] = "signal3_ma7_streak"

        dataframe.loc[signal4, "exit_short"] = 1
        dataframe.loc[signal4, "exit_tag"] = "signal4_ma25_hard_exit"

        return dataframe