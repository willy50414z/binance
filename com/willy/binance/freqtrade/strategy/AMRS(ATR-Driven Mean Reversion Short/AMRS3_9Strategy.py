from datetime import datetime

import numpy as np
import pandas as pd
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import DecimalParameter, IStrategy
from pandas import DataFrame


class AMRS3_9Strategy(IStrategy):
    """
    AMRS v4 / AMRS3_9
    MA7 retrace short strategy with single active exit logic.
    """

    INTERFACE_VERSION = 3

    # Disable ROI based exits. Exit is handled by custom_exit only.
    minimal_roi = {"0": 100}
    stoploss = -0.99
    trailing_stop = False

    timeframe = "15m"
    can_short = True
    process_only_new_candles = True

    # Disable built-in exit signal and rely on custom_exit.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 220

    # Entry params from AMRS3_9.md
    weak_rebound_atr = DecimalParameter(0.3, 0.8, default=0.5, space="buy")
    upper_shadow_atr = DecimalParameter(0.4, 1.2, default=0.7, space="buy")
    recent_low_buffer_atr = DecimalParameter(0.3, 1.0, default=0.5, space="buy")

    # Dynamic ATR risk control.
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

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ma7"] = ta.SMA(dataframe, timeperiod=7)
        dataframe["ma25"] = ta.SMA(dataframe, timeperiod=25)
        dataframe["ma99"] = ta.SMA(dataframe, timeperiod=99)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        dataframe["ma25_slope"] = dataframe["ma25"].diff()
        dataframe["upper_shadow"] = dataframe["high"] - np.maximum(dataframe["open"], dataframe["close"])

        dataframe["prev1_above_ma7"] = dataframe["close"].shift(1) > dataframe["ma7"].shift(1)
        dataframe["prev2_above_ma7"] = dataframe["close"].shift(2) > dataframe["ma7"].shift(2)
        dataframe["prev3_above_ma7"] = dataframe["close"].shift(3) > dataframe["ma7"].shift(3)

        dataframe["recent_low_20"] = dataframe["low"].rolling(window=20).min()
        dataframe["rebound_low_6"] = dataframe["low"].rolling(window=6).min()
        dataframe["pullback_high_6"] = dataframe["high"].rolling(window=6).max()
        dataframe["confirm_midpoint"] = (dataframe["rebound_low_6"] + dataframe["pullback_high_6"]) / 2.0
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

        cond_distance_from_low = (
                (dataframe["close"] - dataframe["recent_low_20"])
                > (self.recent_low_buffer_atr.value * dataframe["atr"])
        )
        cond_bear_body = dataframe["close"] < dataframe["open"]
        cond_confirm_mid = dataframe["close"] < dataframe["confirm_midpoint"]

        cond_entry = (
                cond_trend
                & cond_rebound
                & (cond_signal_a | cond_signal_b)
                & cond_distance_from_low
                & cond_bear_body
                & cond_confirm_mid
        )

        dataframe.loc[cond_entry, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
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

    def custom_exit(
            self,
            pair: str,
            trade: Trade,
            current_time: datetime,
            current_rate: float,
            current_profit: float,
            **kwargs,
    ) -> str | None:
        if not trade.is_short:
            return None

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return None

        current_candle = dataframe.iloc[-1]
        if current_candle["close"] > current_candle["ma7"]:
            return "close_above_ma7"

        return None
