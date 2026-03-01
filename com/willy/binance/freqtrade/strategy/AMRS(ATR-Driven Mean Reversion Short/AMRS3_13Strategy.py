import logging
import math
from datetime import datetime

import pandas as pd
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy
from pandas import DataFrame

logger = logging.getLogger(__name__)


class AMRS3_13Strategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 130

    minimal_roi = {"0": 0}
    stoploss = -0.25
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    trailing_stop = False
    trailing_stop_positive = None
    trailing_stop_positive_offset = None
    trailing_only_offset_is_reached = False

    exit_ma7_confirm_candles = 2
    ma25_slope_candles = 2
    ma99_slope_candles = 2
    min_hold_candles = 30
    hold_loss_release = 0.019
    hold_release_mode = "loss_only"
    timeframe_minutes = 15

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._hold_log_keys: set[tuple[int, str, int]] = set()

    @staticmethod
    def _streak_true(cond: pd.Series) -> pd.Series:
        cond = cond.fillna(False).astype(bool)
        grp = (~cond).cumsum()
        return cond.groupby(grp).cumsum().astype(int)

    @staticmethod
    def _candle_key(ts: datetime, timeframe_minutes: int) -> int:
        return int(ts.timestamp() // (timeframe_minutes * 60))

    def bot_start(self, **kwargs) -> None:
        logger.info(
            "AMRS3_13 start file=%s class=%s trailing_stop=%s exit_confirm=%s slope=%s/%s min_hold=%s loss_release=%s",
            __file__,
            self.__class__.__name__,
            self.trailing_stop,
            self.exit_ma7_confirm_candles,
            self.ma25_slope_candles,
            self.ma99_slope_candles,
            self.min_hold_candles,
            self.hold_loss_release,
        )
        if self.trailing_stop:
            raise ValueError("AMRS3_13Strategy requires trailing_stop=False.")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ma7"] = ta.SMA(dataframe, timeperiod=7)
        dataframe["ma25"] = ta.SMA(dataframe, timeperiod=25)
        dataframe["ma99"] = ta.SMA(dataframe, timeperiod=99)

        dataframe["ma25_slope"] = dataframe["ma25"].diff()
        dataframe["ma99_slope"] = dataframe["ma99"].diff()

        ma25_slope_neg = dataframe["ma25_slope"] < 0
        ma99_slope_neg = dataframe["ma99_slope"] < 0
        dataframe["ma25_slope_neg_streak"] = self._streak_true(ma25_slope_neg)
        dataframe["ma99_slope_neg_streak"] = self._streak_true(ma99_slope_neg)

        dc_ma7_ma25 = (dataframe["ma7"] < dataframe["ma25"]) & (
            dataframe["ma7"].shift(1) >= dataframe["ma25"].shift(1)
        )
        dc_id = dc_ma7_ma25.fillna(False).astype(int).cumsum()
        close_gt_ma7 = (dataframe["close"] > dataframe["ma7"]).fillna(False)
        close_gt_ma7_count_since_dc = close_gt_ma7.astype(int).groupby(dc_id).cumsum()

        dataframe["obs_dc_ma7_below_ma25"] = dc_ma7_ma25.fillna(False).astype(bool)
        dataframe["obs_dc_id"] = dc_id.astype(int)
        dataframe["obs_close_gt_ma7"] = close_gt_ma7.astype(bool)
        dataframe["obs_close_gt_ma7_count_since_dc"] = close_gt_ma7_count_since_dc.astype(int)

        ma7_up = dataframe["close"] > dataframe["ma7"]
        dataframe["ma7_up_streak"] = self._streak_true(ma7_up)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        slope_gate = (
            (dataframe["ma25_slope_neg_streak"] >= self.ma25_slope_candles)
            & (dataframe["ma99_slope_neg_streak"] >= self.ma99_slope_candles)
        )
        entry_core = (
            (dataframe["close"] < dataframe["ma25"])
            & (dataframe["close"] < dataframe["ma7"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[(entry_core & slope_gate).fillna(False), "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        cond_exit = dataframe["ma7_up_streak"] >= self.exit_ma7_confirm_candles
        dataframe.loc[cond_exit.fillna(False), "exit_short"] = 1
        dataframe.loc[cond_exit.fillna(False), "exit_tag"] = "ma7_confirm"
        return dataframe

    def confirm_trade_exit(
        self,
        pair: str,
        trade: Trade,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        exit_reason: str,
        current_time: datetime,
        **kwargs,
    ) -> bool:
        current_profit = float(kwargs.get("current_profit", 0.0))
        held_minutes = (current_time - trade.open_date_utc).total_seconds() / 60.0
        held_candles = math.floor(held_minutes / self.timeframe_minutes)

        if held_candles >= self.min_hold_candles:
            return True

        candle_key = self._candle_key(current_time, self.timeframe_minutes)
        trade_id = int(trade.id or -1)

        if current_profit <= -self.hold_loss_release:
            log_key = (trade_id, "HOLD_RELEASE", candle_key)
            if log_key not in self._hold_log_keys:
                self._hold_log_keys.add(log_key)
                logger.info(
                    "HOLD_RELEASE pair=%s trade_id=%s held_candles=%s profit=%.5f reason=%s",
                    pair,
                    trade.id,
                    held_candles,
                    current_profit,
                    exit_reason,
                )
            return True

        log_key = (trade_id, "HOLD_VETO", candle_key)
        if log_key not in self._hold_log_keys:
            self._hold_log_keys.add(log_key)
            logger.info(
                "HOLD_VETO pair=%s trade_id=%s held_candles=%s profit=%.5f reason=%s",
                pair,
                trade.id,
                held_candles,
                current_profit,
                exit_reason,
            )
        return False
