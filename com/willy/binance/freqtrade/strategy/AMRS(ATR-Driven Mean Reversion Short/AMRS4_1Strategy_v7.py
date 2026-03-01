import logging
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import numpy as np

logger = logging.getLogger(__name__)


class AMRS4_1Strategy_v7(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 120

    # --- 實戰進階控制 ---
    minimal_roi = {"0": 10.0}
    stoploss = -0.05  # 5% 原始止損

    # 移動止盈 (配合 Custom Exit)
    trailing_stop = True
    trailing_stop_positive = 0.003
    trailing_stop_positive_offset = 0.012
    trailing_only_offset_is_reached = True

    # 均線長度
    ma7_len, ma25_len, ma99_len = 7, 25, 99
    lookback_candles = 10
    exit_confirm_candles = 3

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. 均線與斜率
        dataframe["ma7"] = ta.SMA(dataframe, timeperiod=self.ma7_len)
        dataframe["ma25"] = ta.SMA(dataframe, timeperiod=self.ma25_len)
        dataframe["ma99"] = ta.SMA(dataframe, timeperiod=self.ma99_len)
        dataframe["ma7_slope"] = dataframe["ma7"].diff()
        dataframe["ma25_slope"] = dataframe["ma25"].diff()

        # 2. 波動率 (ATR), RSI 與 成交量均線
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=5).mean()

        # 3. 價格過濾
        dataframe['body_min'] = np.minimum(dataframe['open'], dataframe['close'])
        dataframe['ten_candle_low'] = dataframe['body_min'].shift(1).rolling(window=self.lookback_candles).min()
        dataframe['body_size'] = dataframe['open'] - dataframe['close']

        # 4. 出場狀態計數
        dataframe["close_gt_ma7"] = dataframe["close"] > dataframe["ma7"]
        dataframe["streak_ma7"] = self._streak_true(dataframe["close_gt_ma7"])

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 【動態進場邏輯】
        # 條件 A: 常規趨勢與破底
        # 條件 B: RSI > 25 (非超賣) OR 成交量爆發 (恐慌性破位)

        base_filter = (
                (dataframe["close"] < dataframe["ma99"]) &
                (dataframe["ma7"] < dataframe["ma25"]) &
                (dataframe["ma7_slope"] < 0) &
                (dataframe["ma25_slope"] < 0) &
                (dataframe["close"] < dataframe["ten_candle_low"]) &
                (dataframe["body_size"] >= (dataframe['atr'] * 1.5))
        )

        momentum_confirm = (
                (dataframe["rsi"] > 25) |
                (dataframe["volume"] > dataframe["volume_mean"] * 2.0)
        )

        entry_condition = base_filter & momentum_confirm

        dataframe.loc[entry_condition, "enter_short"] = 1
        dataframe.loc[entry_condition, "enter_tag"] = "v7_hybrid_entry"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 常規 3 根 K 棒站上 MA7 出場
        dataframe.loc[dataframe["streak_ma7"] >= self.exit_confirm_candles, "exit_short"] = 1
        dataframe.loc[dataframe["streak_ma7"] >= self.exit_confirm_candles, "exit_tag"] = "exit_ma7_streak"

        # MA25 止損 (加入 0.15% 緩衝，避免影線掃單)
        dataframe.loc[dataframe["close"] > (dataframe["ma25"] * 1.0015), "exit_short"] = 1
        dataframe.loc[dataframe["close"] > (dataframe["ma25"] * 1.0015), "exit_tag"] = "exit_ma25_buffer"

        return dataframe

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        # 【敏捷止盈機制】
        # 只要獲利 > 0.8%，一旦有一根收盤高於 MA7，立刻結算
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        if current_profit > 0.008:
            if last_candle['close'] > last_candle['ma7']:
                return "quick_profit_exit"

        return None

    @staticmethod
    def _streak_true(cond: pd.Series) -> pd.Series:
        cond = cond.fillna(False).astype(bool)
        grp = (~cond).cumsum()
        return cond.groupby(grp).cumsum().astype(int)