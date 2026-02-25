import logging
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy, merge_informative_pair
from pandas import DataFrame
import numpy as np

logger = logging.getLogger(__name__)


class AMRS4_1Strategy_v10(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 120

    # --- 交易性能參數 ---
    minimal_roi = {"0": 10.0}
    stoploss = -0.05  # 5% 原始止損

    trailing_stop = True
    trailing_stop_positive = 0.002
    trailing_stop_positive_offset = 0.010
    trailing_only_offset_is_reached = True

    # 參數設定
    ma7_len, ma25_len, ma99_len = 7, 25, 99
    lookback_candles = 10
    exit_confirm_candles = 3

    def informative_pairs(self):
        return [(self.config['stake_currency'], '1d')]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 1. 日線指標 (1D) ---
        informative = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='1d')
        informative['ma25_day'] = ta.SMA(informative, timeperiod=25)
        informative['day_slope'] = informative['ma25_day'].diff()

        # 新增 ADX 用於判斷趨勢強度 (避開震盪)
        informative['adx'] = ta.ADX(informative, timeperiod=14)
        informative['plus_di'] = ta.PLUS_DI(informative, timeperiod=14)
        informative['minus_di'] = ta.MINUS_DI(informative, timeperiod=14)

        dataframe = merge_informative_pair(dataframe, informative, self.timeframe, '1d', ffill=True)

        # --- 2. 15m 基礎指標 ---
        dataframe["ma7"] = ta.SMA(dataframe, timeperiod=self.ma7_len)
        dataframe["ma25"] = ta.SMA(dataframe, timeperiod=self.ma25_len)
        dataframe["ma99"] = ta.SMA(dataframe, timeperiod=self.ma99_len)
        dataframe["ma7_slope"] = dataframe["ma7"].diff()
        dataframe["ma25_slope"] = dataframe["ma25"].diff()

        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=5).mean()

        dataframe['body_min'] = np.minimum(dataframe['open'], dataframe['close'])
        dataframe['ten_candle_low'] = dataframe['body_min'].shift(1).rolling(window=self.lookback_candles).min()
        dataframe['body_size'] = dataframe['open'] - dataframe['close']

        dataframe["close_gt_ma7"] = dataframe["close"] > dataframe["ma7"]
        dataframe["streak_ma7"] = self._streak_true(dataframe["close_gt_ma7"])

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 15m 形態條件
        base_filter = (
                (dataframe["close"] < dataframe["ma99"]) &
                (dataframe["ma7"] < dataframe["ma25"]) &
                (dataframe["ma7_slope"] < 0) &
                (dataframe["ma25_slope"] < 0) &
                (dataframe["close"] < dataframe["ten_candle_low"]) &
                (dataframe["body_size"] >= (dataframe['atr'] * 1.4))
        )

        momentum_confirm = (
                (dataframe["rsi"] > 25) |
                (dataframe["volume"] > dataframe["volume_mean"] * 1.8)
        )

        # 【v10 核心：雙重日線過濾】
        # 條件 A: 日線 MA25 斜率向下 (方向判斷)
        # 條件 B: 日線 ADX > 18 且 -DI > +DI (強度判斷，避開無方向震盪)
        macro_filter = (
                (dataframe['day_slope_1d'] <= 0) &
                (dataframe['adx_1d'] > 18) &
                (dataframe['minus_di_1d'] > dataframe['plus_di_1d'])
        )

        entry_condition = base_filter & momentum_confirm & macro_filter

        dataframe.loc[entry_condition, "enter_short"] = 1
        dataframe.loc[entry_condition, "enter_tag"] = "v10_shield_entry"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["streak_ma7"] >= self.exit_confirm_candles, "exit_short"] = 1
        dataframe.loc[dataframe["close"] > (dataframe["ma25"] * 1.0015), "exit_short"] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        if current_profit > 0.007 and last_candle['close'] > last_candle['ma7']:
            return "v10_quick_profit"
        return None

    @staticmethod
    def _streak_true(cond: pd.Series) -> pd.Series:
        cond = cond.fillna(False).astype(bool)
        grp = (~cond).cumsum()
        return cond.groupby(grp).cumsum().astype(int)