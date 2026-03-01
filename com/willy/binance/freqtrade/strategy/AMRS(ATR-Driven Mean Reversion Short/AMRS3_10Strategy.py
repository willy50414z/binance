from datetime import datetime

import numpy as np
import pandas as pd
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    IStrategy,
)
from pandas import DataFrame


class AMRS3_10Strategy(IStrategy):
    """
    AMRS v4 / AMRS3_10
    Focus: reduce range trades and noisy MA7 exits.
    """

    INTERFACE_VERSION = 3

    minimal_roi = {"0": 100}
    stoploss = -0.99
    trailing_stop = False

    timeframe = "15m"
    can_short = True
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 260

    # Base AMRS entry params
    weak_rebound_atr = DecimalParameter(0.3, 0.8, default=0.5, space="buy")
    upper_shadow_atr = DecimalParameter(0.4, 1.2, default=0.7, space="buy")
    recent_low_buffer_atr = DecimalParameter(0.3, 1.0, default=0.5, space="buy")

    # A) Trend/range filters
    use_ma_stack_filter = BooleanParameter(default=True, space="buy")
    use_ma_gap_filter = BooleanParameter(default=True, space="buy")
    min_ma7_ma25_gap = DecimalParameter(0.0002, 0.01, default=0.0010, decimals=4, space="buy")
    min_ma25_ma99_gap = DecimalParameter(0.0002, 0.015, default=0.0015, decimals=4, space="buy")
    use_price_dist_filter = BooleanParameter(default=True, space="buy")
    min_price_below_ma7 = DecimalParameter(0.0002, 0.01, default=0.0010, decimals=4, space="buy")

    # B) MA7 downtrend streak (N=0 => off)
    ma7_downtrend_candles = IntParameter(0, 24, default=6, space="buy")

    # C) Relative volume filter
    use_volume_filter = BooleanParameter(default=False, space="buy")
    volume_filter_mode = CategoricalParameter(["max", "band"], default="max", space="buy")
    vol_window = IntParameter(10, 80, default=20, space="buy")
    vol_ratio_max = DecimalParameter(0.8, 2.5, default=1.6, decimals=2, space="buy")
    vol_ratio_low = DecimalParameter(0.1, 1.2, default=0.4, decimals=2, space="buy")
    vol_ratio_high = DecimalParameter(0.8, 3.0, default=1.8, decimals=2, space="buy")

    # D) Exit anti-whipsaw
    exit_mode = CategoricalParameter(["ma7", "ma7_confirm"], default="ma7_confirm", space="sell")
    exit_ma7_confirm_candles = IntParameter(2, 6, default=3, space="sell")

    # Dynamic ATR risk control
    base_sl_atr = DecimalParameter(0.8, 2.0, default=1.2, space="sell")
    max_initial_sl = DecimalParameter(0.015, 0.03, default=0.03, space="sell")

    @property
    def protections(self):
        return [
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 200,
                "trade_limit": 3,
                "stop_duration_candles": 10,
                "only_per_pair": True,
            }
        ]

    @staticmethod
    def _true_series(dataframe: DataFrame) -> pd.Series:
        return pd.Series(True, index=dataframe.index)

    @staticmethod
    def _streak_true(cond: pd.Series) -> pd.Series:
        grp = (~cond).cumsum()
        return cond.groupby(grp).cumsum()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ma7"] = ta.SMA(dataframe, timeperiod=7)
        dataframe["ma25"] = ta.SMA(dataframe, timeperiod=25)
        dataframe["ma99"] = ta.SMA(dataframe, timeperiod=99)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        dataframe["ma25_slope"] = dataframe["ma25"].diff()
        dataframe["ma7_slope"] = dataframe["ma7"].diff()
        dataframe["upper_shadow"] = dataframe["high"] - np.maximum(dataframe["open"], dataframe["close"])

        dataframe["prev1_above_ma7"] = dataframe["close"].shift(1) > dataframe["ma7"].shift(1)
        dataframe["prev2_above_ma7"] = dataframe["close"].shift(2) > dataframe["ma7"].shift(2)
        dataframe["prev3_above_ma7"] = dataframe["close"].shift(3) > dataframe["ma7"].shift(3)

        dataframe["recent_low_20"] = dataframe["low"].rolling(window=20).min()
        dataframe["rebound_low_6"] = dataframe["low"].rolling(window=6).min()
        dataframe["pullback_high_6"] = dataframe["high"].rolling(window=6).max()
        dataframe["confirm_midpoint"] = (dataframe["rebound_low_6"] + dataframe["pullback_high_6"]) / 2.0

        dataframe["d_7_25"] = (dataframe["ma7"] - dataframe["ma25"]).abs() / dataframe["close"].replace(0, np.nan)
        dataframe["d_25_99"] = (dataframe["ma25"] - dataframe["ma99"]).abs() / dataframe["close"].replace(0, np.nan)
        dataframe["price_below_ma7"] = (dataframe["ma7"] - dataframe["close"]) / dataframe["close"].replace(0, np.nan)

        vw = int(self.vol_window.value)
        dataframe["vol_sma"] = dataframe["volume"].rolling(window=vw).mean()
        dataframe["vol_ratio"] = dataframe["volume"] / dataframe["vol_sma"].replace(0, np.nan)

        dataframe["above_ma7"] = dataframe["close"] > dataframe["ma7"]
        dataframe["above_ma7_streak"] = self._streak_true(dataframe["above_ma7"].fillna(False))
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        cond_trend = (
            (dataframe["close"] < dataframe["ma7"])
            & (dataframe["ma7"] < dataframe["ma25"])
            & (dataframe["ma25"] < dataframe["ma99"])
            & (dataframe["ma25_slope"] < 0)
        )

        cond_rebound = (dataframe["close"] - dataframe["ma7"]).abs() <= (
            self.weak_rebound_atr.value * dataframe["atr"]
        )

        cond_signal_a = (
            (dataframe["high"] > dataframe["ma7"])
            & (dataframe["upper_shadow"] > self.upper_shadow_atr.value * dataframe["atr"])
        )
        cond_signal_b = (
            (dataframe["close"] < dataframe["ma7"])
            & (
                dataframe["prev1_above_ma7"]
                | dataframe["prev2_above_ma7"]
                | dataframe["prev3_above_ma7"]
            )
        )
        cond_signal = cond_signal_a | cond_signal_b

        cond_distance_from_low = (
            (dataframe["close"] - dataframe["recent_low_20"])
            > (self.recent_low_buffer_atr.value * dataframe["atr"])
        )
        cond_bear_body = dataframe["close"] < dataframe["open"]
        cond_confirm_mid = dataframe["close"] < dataframe["confirm_midpoint"]

        # A) Optional stack / gap / price-distance filters
        cond_ma_stack = (
            (dataframe["ma7"] < dataframe["ma25"]) & (dataframe["ma25"] < dataframe["ma99"])
            if self.use_ma_stack_filter.value
            else self._true_series(dataframe)
        )
        cond_ma_gap = (
            (dataframe["d_7_25"] > float(self.min_ma7_ma25_gap.value))
            & (dataframe["d_25_99"] > float(self.min_ma25_ma99_gap.value))
            if self.use_ma_gap_filter.value
            else self._true_series(dataframe)
        )
        cond_price_dist = (
            dataframe["price_below_ma7"] > float(self.min_price_below_ma7.value)
            if self.use_price_dist_filter.value
            else self._true_series(dataframe)
        )

        # B) MA7 downtrend continuous confirmation
        n_down = int(self.ma7_downtrend_candles.value)
        if n_down > 0:
            cond_ma7_down = (dataframe["ma7_slope"] < 0).rolling(window=n_down).sum() >= n_down
        else:
            cond_ma7_down = self._true_series(dataframe)

        # C) Relative volume filter
        if self.use_volume_filter.value:
            if self.volume_filter_mode.value == "band":
                cond_volume = (
                    (dataframe["vol_ratio"] >= float(self.vol_ratio_low.value))
                    & (dataframe["vol_ratio"] <= float(self.vol_ratio_high.value))
                )
            else:
                cond_volume = dataframe["vol_ratio"] <= float(self.vol_ratio_max.value)
        else:
            cond_volume = self._true_series(dataframe)

        cond_entry = (
            cond_trend
            & cond_rebound
            & cond_signal
            & cond_distance_from_low
            & cond_bear_body
            & cond_confirm_mid
            & cond_ma_stack
            & cond_ma_gap
            & cond_price_dist
            & cond_ma7_down
            & cond_volume
        )

        dataframe.loc[cond_entry.fillna(False), "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        if self.exit_mode.value == "ma7_confirm":
            confirm_n = int(self.exit_ma7_confirm_candles.value)
            cond_exit = dataframe["above_ma7_streak"] >= confirm_n
        else:
            cond_exit = dataframe["above_ma7"]

        dataframe.loc[cond_exit.fillna(False), "exit_short"] = 1
        return dataframe

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        if side != "short":
            return 0.0

        wallet = self.wallets.get_total_stake_amount()
        risk_budget = wallet * 0.02
        assumed_sl = 0.02
        stake = risk_budget / max(assumed_sl, 1e-6)
        stake = min(stake, max_stake)
        if min_stake is not None:
            stake = max(stake, min_stake)
        return float(stake)

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        if not trade.is_short:
            return 1

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return 1

        current_candle = dataframe.iloc[-1]
        atr = current_candle["atr"]
        if pd.isna(atr) or trade.open_rate <= 0:
            return 1

        atr_sl_ratio = float(self.base_sl_atr.value * atr / trade.open_rate)
        sl_ratio = min(atr_sl_ratio, float(self.max_initial_sl.value))
        return -float(sl_ratio)
