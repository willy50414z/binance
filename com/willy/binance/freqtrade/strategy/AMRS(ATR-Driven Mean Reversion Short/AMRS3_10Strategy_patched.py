from datetime import datetime

import json
import logging
import os
from pathlib import Path

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

LOGGER = logging.getLogger(__name__)


class AMRS3_10Strategy_patched(IStrategy):
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
    use_custom_stoploss = False

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

    # B2) MA slope filter
    use_ma_slope_filter = BooleanParameter(default=False, space="buy")
    ma25_slope_candles = IntParameter(0, 12, default=0, space="buy")
    ma99_slope_candles = IntParameter(0, 12, default=0, space="buy")

    # C) Relative volume filter
    use_volume_filter = BooleanParameter(default=False, space="buy")
    volume_filter_mode = CategoricalParameter(["avoid_spike", "band"], default="avoid_spike", space="buy")
    vol_window = IntParameter(10, 80, default=20, space="buy")
    vol_ratio_max = DecimalParameter(0.8, 2.5, default=1.6, decimals=2, space="buy")
    vol_ratio_low = DecimalParameter(0.1, 1.2, default=0.4, decimals=2, space="buy")
    vol_ratio_high = DecimalParameter(0.8, 3.0, default=1.8, decimals=2, space="buy")

    # D) Exit anti-whipsaw
    exit_mode = CategoricalParameter(["ma7", "ma7_confirm"], default="ma7_confirm", space="sell")
    exit_ma7_confirm_candles = IntParameter(2, 6, default=3, space="sell")
    min_hold_candles = IntParameter(0, 60, default=0, space="sell")
    hold_release_mode = CategoricalParameter(["none", "loss_only", "loss_or_profit"], default="loss_only", space="sell")
    hold_loss_release = DecimalParameter(0.005, 0.05, default=0.02, decimals=3, space="sell")
    hold_profit_release = DecimalParameter(0.002, 0.05, default=0.01, decimals=3, space="sell")

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

    @staticmethod
    def _parse_bool(value) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            norm = value.strip().lower()
            if norm in {"1", "true", "t", "yes", "y", "on"}:
                return True
            if norm in {"0", "false", "f", "no", "n", "off", ""}:
                return False
        raise ValueError(f"Invalid boolean value: {value!r}")

    def bot_start(self, **kwargs) -> None:
        """Called once when the bot starts (also executed for backtesting/hyperopt).

        Supports external parameter overrides for cross-tests via env var:
          STRATEGY_PARAM_FILE=/path/to/params.json

        JSON format supported:
          - {"params": {"param_name": value, ...}}
          - {"param_name": value, ...}
        """
        param_file, applied = self._load_param_overrides_from_env()
        self._assert_stage4_runtime_safety()
        self._log_effective_params(param_file, applied)

    def _runtime_trailing_stop_enabled(self) -> bool:
        runtime_value = bool(getattr(self, "trailing_stop", False))
        config_dict = getattr(self, "config", None)
        cfg_value = None
        if isinstance(config_dict, dict):
            cfg_value = config_dict.get("trailing_stop")

        if cfg_value is None:
            return runtime_value

        try:
            return runtime_value or self._parse_bool(cfg_value)
        except Exception:
            LOGGER.warning("Invalid trailing_stop value in config: %r", cfg_value)
            return runtime_value

    def _assert_stage4_runtime_safety(self) -> None:
        if not self._runtime_trailing_stop_enabled():
            return

        msg = "Trailing stop is enabled but Stage4 expects MA exit."
        LOGGER.error(msg)
        raise ValueError(msg)

    def _load_param_overrides_from_env(self) -> tuple[str, int]:
        param_file = os.getenv("STRATEGY_PARAM_FILE")
        if not param_file:
            return "", 0

        p = Path(param_file).expanduser()
        if not p.exists() or not p.is_file():
            LOGGER.warning("STRATEGY_PARAM_FILE=%s not found or not a file.", param_file)
            return str(p), 0

        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            LOGGER.exception("Failed to read STRATEGY_PARAM_FILE=%s: %s", str(p), e)
            return str(p), 0

        overrides = raw.get("params", raw) if isinstance(raw, dict) else None
        if not isinstance(overrides, dict):
            LOGGER.warning("STRATEGY_PARAM_FILE=%s has invalid JSON structure (expect dict).", str(p))
            return str(p), 0

        applied = 0
        for key, val in overrides.items():
            if not hasattr(self, key):
                continue
            attr = getattr(self, key)
            # freqtrade Parameter objects have `.value`
            if not hasattr(attr, "value"):
                continue

            try:
                # Cast by Parameter type
                if isinstance(attr, BooleanParameter):
                    attr.value = self._parse_bool(val)
                elif isinstance(attr, IntParameter):
                    attr.value = int(val)
                elif isinstance(attr, DecimalParameter):
                    attr.value = float(val)
                elif isinstance(attr, CategoricalParameter):
                    attr.value = val
                else:
                    # fallback
                    attr.value = val
                applied += 1
            except Exception as e:
                LOGGER.warning("Failed to apply override %s=%r: %s", key, val, e)

        LOGGER.info("Applied %d strategy param overrides from %s", applied, str(p))
        return str(p), applied

    def _effective_params_payload(self) -> dict:
        return {
            "use_ma_slope_filter": bool(self.use_ma_slope_filter.value),
            "ma25_slope_candles": int(self.ma25_slope_candles.value),
            "ma99_slope_candles": int(self.ma99_slope_candles.value),
            "exit_mode": str(self.exit_mode.value),
            "exit_ma7_confirm_candles": int(self.exit_ma7_confirm_candles.value),
            "min_hold_candles": int(self.min_hold_candles.value),
            "hold_release_mode": str(self.hold_release_mode.value),
            "hold_loss_release": float(self.hold_loss_release.value),
            "hold_profit_release": float(self.hold_profit_release.value),
            "trailing_stop": bool(getattr(self, "trailing_stop", False)),
        }

    def _log_effective_params(self, param_file: str, applied: int) -> None:
        LOGGER.info("Strategy file: %s", __file__)
        LOGGER.info("Strategy class: %s", self.__class__.__name__)
        LOGGER.info("STRATEGY_PARAM_FILE=%s", param_file or "")
        LOGGER.info("Applied override keys: %d", applied)
        LOGGER.info("Effective params: %s", json.dumps(self._effective_params_payload(), ensure_ascii=False, sort_keys=True))

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
            (dataframe["close"] < dataframe["ma7"]) & (dataframe["ma25_slope"] < 0)
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

        # B2) MA25/MA99 slope gate
        if self.use_ma_slope_filter.value:
            n25 = max(1, int(self.ma25_slope_candles.value))
            n99 = max(1, int(self.ma99_slope_candles.value))
            cond_ma25_down = (dataframe["ma25_slope"] < 0).rolling(window=n25).sum() >= n25
            cond_ma99_down = (dataframe["ma99"].diff() < 0).rolling(window=n99).sum() >= n99
            cond_ma_slope = cond_ma25_down & cond_ma99_down
        else:
            cond_ma_slope = self._true_series(dataframe)

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
            & cond_ma_slope
            & cond_volume
        )

        dataframe.loc[cond_entry.fillna(False), "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        dataframe["exit_tag"] = ""

        if self.exit_mode.value == "ma7_confirm":
            confirm_n = int(self.exit_ma7_confirm_candles.value)
            cond_exit = dataframe["above_ma7_streak"] >= confirm_n
            exit_tag = "ma7_confirm"
        else:
            cond_exit = dataframe["above_ma7"]
            exit_tag = "ma7"

        dataframe.loc[cond_exit.fillna(False), "exit_short"] = 1
        dataframe.loc[cond_exit.fillna(False), "exit_tag"] = exit_tag
        return dataframe

    @staticmethod
    def _normalize_ts(value: datetime | pd.Timestamp | None) -> pd.Timestamp | None:
        if value is None:
            return None
        try:
            ts = pd.Timestamp(value)
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            else:
                ts = ts.tz_convert("UTC")
            return ts
        except Exception:
            return None

    def _timeframe_minutes(self) -> int:
        tf = str(getattr(self, "timeframe", "15m") or "15m").strip().lower()
        if not tf:
            return 15
        unit = tf[-1]
        raw_value = tf[:-1]
        try:
            value = int(raw_value)
        except Exception:
            return 15
        if value <= 0:
            return 15
        if unit == "m":
            return value
        if unit == "h":
            return value * 60
        if unit == "d":
            return value * 24 * 60
        if unit == "w":
            return value * 7 * 24 * 60
        return 15

    def _held_candles(self, dataframe: DataFrame, trade: Trade, current_time: datetime) -> int | None:
        now_ts = self._normalize_ts(current_time)
        open_ts = self._normalize_ts(getattr(trade, "open_date_utc", None))
        if now_ts is None or open_ts is None:
            return None

        timeframe_minutes = self._timeframe_minutes()
        delta_minutes = (now_ts - open_ts).total_seconds() / 60.0
        if delta_minutes < 0:
            return None
        fallback = int(delta_minutes // timeframe_minutes)

        if dataframe.empty or "date" not in dataframe.columns:
            return fallback

        date_index = pd.DatetimeIndex(pd.to_datetime(dataframe["date"], utc=True, errors="coerce"))
        if date_index.isna().all():
            return fallback

        current_idx = int(date_index.searchsorted(now_ts, side="right") - 1)
        open_idx = int(date_index.searchsorted(open_ts, side="right") - 1)
        if current_idx < 0 or open_idx < 0 or current_idx < open_idx:
            return fallback
        return current_idx - open_idx

    def _is_hold_veto(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        exit_reason: str | None,
        current_profit: float | None = None,
    ) -> bool:
        if not trade.is_short:
            return False
        min_hold = max(0, int(self.min_hold_candles.value))
        if min_hold <= 0:
            return False

        dataframe = DataFrame()
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        except Exception:
            dataframe = DataFrame()

        held_candles = self._held_candles(dataframe, trade, current_time)
        if held_candles is None or held_candles >= min_hold:
            return False

        mode = str(self.hold_release_mode.value)
        loss_release = max(0.0, float(self.hold_loss_release.value))
        profit_release = max(0.0, float(self.hold_profit_release.value))

        release_reason = ""
        cp = current_profit
        if cp is not None:
            if mode == "loss_only" and cp <= -loss_release:
                release_reason = "loss_release"
            elif mode == "loss_or_profit":
                if cp <= -loss_release:
                    release_reason = "loss_release"
                elif cp >= profit_release:
                    release_reason = "profit_release"
        if release_reason:
            LOGGER.info(
                "HOLD_RELEASE: pair=%s held_candles=%s min_hold=%s current_profit=%.6f reason=%s",
                pair,
                held_candles,
                min_hold,
                cp if cp is not None else 0.0,
                release_reason,
            )
            return False

        cp_text = "NA" if cp is None else f"{cp:.6f}"
        LOGGER.info(
            "HOLD_VETO: pair=%s held_candles=%s min_hold=%s current_profit=%s exit_reason=%s mode=%s",
            pair,
            held_candles,
            min_hold,
            cp_text,
            str(exit_reason or ""),
            mode,
        )
        return True

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

        held_candles = self._held_candles(dataframe, trade, current_time)
        min_hold = max(0, int(self.min_hold_candles.value))
        if held_candles is not None and held_candles < min_hold:
            return None

        if self.exit_mode.value == "ma7_confirm":
            confirm_n = max(1, int(self.exit_ma7_confirm_candles.value))
            window = dataframe.tail(confirm_n)
            if len(window.index) < confirm_n:
                return None
            cond = (window["close"] > window["ma7"]).fillna(False)
            if bool(cond.all()):
                return "ma7_confirm"
            if held_candles is not None:
                timeout_candles = max(min_hold + 16, min_hold + confirm_n * 4)
                if held_candles >= timeout_candles:
                    return "ma7_confirm"
            return None

        last = dataframe.iloc[-1]
        if bool((last["close"] > last["ma7"]) if "ma7" in dataframe.columns else False):
            return "ma7"
        return None

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
        _ = order_type
        _ = amount
        _ = rate
        _ = time_in_force
        _ = kwargs
        current_profit = None
        try:
            current_profit = float(trade.calc_profit_ratio(rate))
        except Exception:
            current_profit = None
        return not self._is_hold_veto(
            pair=pair,
            trade=trade,
            current_time=current_time,
            exit_reason=exit_reason,
            current_profit=current_profit,
        )

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
