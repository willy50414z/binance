import logging
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import numpy as np

logger = logging.getLogger(__name__)


class AMRS4_1Strategy_v8(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 120

    # --- 核心性能參數 ---
    minimal_roi = {"0": 10.0}
    stoploss = -0.05  # 5% 全域止損

    # 優化後的移動止盈：1.0% 啟動，回撤 0.2% 即出場
    trailing_stop = True
    trailing_stop_positive = 0.002
    trailing_stop_positive_offset = 0.010
    trailing_only_offset_is_reached = True

    # 均線與過濾參數
    ma7_len, ma25_len, ma99_len = 7, 25, 99
    lookback_candles = 10
    exit_confirm_candles = 3

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. 均線系統
        dataframe["ma7"] = ta.SMA(dataframe, timeperiod=self.ma7_len)
        dataframe["ma25"] = ta.SMA(dataframe, timeperiod=self.ma25_len)
        dataframe["ma99"] = ta.SMA(dataframe, timeperiod=self.ma99_len)
        dataframe["ma7_slope"] = dataframe["ma7"].diff()
        dataframe["ma25_slope"] = dataframe["ma25"].diff()

        # 2. 波動與動能
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=5).mean()

        # 3. 實體破底過濾
        dataframe['body_min'] = np.minimum(dataframe['open'], dataframe['close'])
        dataframe['ten_candle_low'] = dataframe['body_min'].shift(1).rolling(window=self.lookback_candles).min()
        dataframe['body_size'] = dataframe['open'] - dataframe['close']

        # 4. 出場計數
        dataframe["close_gt_ma7"] = dataframe["close"] > dataframe["ma7"]
        dataframe["streak_ma7"] = self._streak_true(dataframe["close_gt_ma7"])

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 進場條件：趨勢向下 + 破底 + (RSI安全區 OR 恐慌放量)
        base_filter = (
                (dataframe["close"] < dataframe["ma99"]) &
                (dataframe["ma7"] < dataframe["ma25"]) &
                (dataframe["ma7_slope"] < 0) &
                (dataframe["ma25_slope"] < 0) &
                (dataframe["close"] < dataframe["ten_candle_low"]) &
                (dataframe["body_size"] >= (dataframe['atr'] * 1.4))  # 稍微放寬至 1.4
        )

        momentum_confirm = (
                (dataframe["rsi"] > 25) |
                (dataframe["volume"] > dataframe["volume_mean"] * 1.8)  # 恐慌放量門檻微調
        )

        entry_condition = base_filter & momentum_confirm

        dataframe.loc[entry_condition, "enter_short"] = 1
        dataframe.loc[entry_condition, "enter_tag"] = "v8_master_entry"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 常規出場：連續 3 根站上 MA7
        dataframe.loc[dataframe["streak_ma7"] >= self.exit_confirm_candles, "exit_short"] = 1
        dataframe.loc[dataframe["streak_ma7"] >= self.exit_confirm_candles, "exit_tag"] = "ma7_streak_exit"

        # MA25 止損緩衝
        dataframe.loc[dataframe["close"] > (dataframe["ma25"] * 1.0015), "exit_short"] = 1
        dataframe.loc[dataframe["close"] > (dataframe["ma25"] * 1.0015), "exit_tag"] = "ma25_buffer_stop"

        return dataframe

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        # 敏捷止盈：獲利 > 0.7% 後，只要 1 根收盤 > MA7 就走 (比 v7 更敏銳)
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        if current_profit > 0.007:
            if last_candle['close'] > last_candle['ma7']:
                return "v8_quick_profit"

        return None

    @staticmethod
    def _streak_true(cond: pd.Series) -> pd.Series:
        cond = cond.fillna(False).astype(bool)
        grp = (~cond).cumsum()
        return cond.groupby(grp).cumsum().astype(int)