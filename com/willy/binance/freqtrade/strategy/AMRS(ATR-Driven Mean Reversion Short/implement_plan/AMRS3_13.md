# Codex Request: Build Freqtrade Strategy (Best Params + Observation Signal)

## Goal
Create a Freqtrade `IStrategy` (short-only) implementing the current best parameter combination:
- Exit: MA7 confirm (2 consecutive closes > MA7) for short exit
- Entry: keep a working short entry core AND apply slope gate (ma25/ma99 slope negative streak 2/2)
- Hold gate: min_hold_candles = 30 (timeframe 15m)
- Loss-release: allow exit before hold if current_profit <= -0.019 (loss_only)
- Trailing stop MUST be disabled and self-checked at start (raise if enabled)

Additionally: Add an observation-only signal column:
- Observe: "MA7 death crosses MA25" event
- After each death cross, count how many candles have `close > MA7`
- This count must be written into the dataframe (signals export), but MUST NOT affect entry/exit logic.

Deliver a single Python file strategy: `AMRS_Best_v1.py`.

---

## Environment / Defaults
- timeframe: "15m"
- can_short: True
- process_only_new_candles: True
- startup_candle_count: at least 120 (needs MA99)
- use `talib.abstract as ta` or pandas calculations

---

## Fixed Parameters (DO NOT expose as optimizable; hardcode values)
### Exit (sell)
- exit_mode = "ma7_confirm" (fixed)
- exit_ma7_confirm_candles = 2 (fixed)

### Entry slope gate (buy filter)
- use_ma_slope_filter = True
- ma25_slope_candles = 2
- ma99_slope_candles = 2

### Hold + loss-release (sell veto)
- min_hold_candles = 30
- hold_release_mode = "loss_only"
- hold_loss_release = 0.019

### Trailing must be disabled
- trailing_stop = False
- trailing_stop_positive = None
- trailing_stop_positive_offset = None
- trailing_only_offset_is_reached = False
On startup, if trailing_stop is True at runtime, raise ValueError.

### Stoploss / ROI (keep simple)
- stoploss: set a safe fixed value (e.g. -0.25)
- minimal_roi: can be empty or {"0": 0} (we rely on exit signals)
- use_exit_signal = True
- exit_profit_only = False
- ignore_roi_if_entry_signal = False

---

## Indicators (populate_indicators)
Compute:
- ma7 = SMA(close, 7)
- ma25 = SMA(close, 25)
- ma99 = SMA(close, 99)
- ma25_slope = ma25.diff()
- ma99_slope = ma99.diff()

Implement helper `_streak_true(bool_series)` returning consecutive-True count (reset to 0 when False):
- ma25_slope_neg = ma25_slope < 0
- ma99_slope_neg = ma99_slope < 0
- ma25_slope_neg_streak = _streak_true(ma25_slope_neg)
- ma99_slope_neg_streak = _streak_true(ma99_slope_neg)

### Observation-only signals (must be added to dataframe)
We observe:
1) Death cross event: MA7 crosses below MA25
   - `dc_ma7_ma25 = (ma7 < ma25) & (ma7.shift(1) >= ma25.shift(1))`
2) Segment id after each death cross:
   - `dc_id = dc_ma7_ma25.cumsum()`
3) Condition to count: close > ma7
   - `close_gt_ma7 = close > ma7`
4) Count occurrences since last death cross:
   - `close_gt_ma7_count_since_dc = close_gt_ma7.groupby(dc_id).cumsum()`
5) Also output whether we are in post-death-cross regime (dc_id > 0)

Add these columns with exact names:
- `obs_dc_ma7_below_ma25` (bool)
- `obs_dc_id` (int)
- `obs_close_gt_ma7` (bool)
- `obs_close_gt_ma7_count_since_dc` (int)

NOTE: The observation columns MUST NOT be used in entry/exit conditions (for now).
They are only for signals export and later analysis.

---

## Entry logic (populate_entry_trend)
Implement a minimal working short entry core plus slope gate:
- slope_gate = (ma25_slope_neg_streak >= 2) & (ma99_slope_neg_streak >= 2)

Entry core: Use a simple, deterministic short entry that creates trades in backtest.
Example placeholder (acceptable):
- `close < ma25` AND `close < ma7` AND `volume > 0`
(Or use RSI/ATR if you prefer, but keep it stable and not too restrictive.)

Final:
- `enter_short = 1` when `entry_core & slope_gate`

Also set:
- `enter_long = 0` always

---

## Exit logic (populate_exit_trend)
MA7 confirm for short exit:
- `ma7_up = (close > ma7)`
- `ma7_up_streak = _streak_true(ma7_up)`
- `exit_short = 1` when `ma7_up_streak >= 2`
Also set:
- `exit_long = 0` always

Optionally set a column:
- `exit_tag = "ma7_confirm"` when exit_short

---

## Hold + Loss-release Veto (confirm_trade_exit)
Implement `confirm_trade_exit(...) -> bool` to veto exit before hold:
- timeframe_minutes = 15
- held_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
- held_candles = floor(held_minutes / 15)

Rules:
1) If held_candles >= 30: allow exit (return True)
2) Else (held_candles < 30):
   - if current_profit <= -0.019: allow exit (loss-release) (return True)
   - else: veto exit (return False)

Logging (must include, but avoid spamming: throttle per trade per candle if possible):
- `HOLD_VETO` lines
- `HOLD_RELEASE` lines

---

## Startup Logging / Self-check
On `bot_start()` (or `__init__` if needed), log:
- strategy file path, class name
- trailing_stop state
- fixed params (exit confirm=2, slope=2/2, min_hold=30, loss_release=0.019)
If trailing_stop enabled at runtime -> raise ValueError.

---

## Output requirements
- Provide the full code of `AMRS_Best_v1.py` in one file.
- Must be runnable by Freqtrade without other dependencies.
- Must include imports, class definition, helper functions.

---

## Backtest expectation (acceptance)
When running:
`freqtrade backtesting --strategy AMRS_Best_v1 --export trades signals ...`
- signals dataframe should contain the obs_* columns
- trades should show exit reason mainly due to exit_signal (ma7_confirm), not trailing
- hold_veto_count > 0, hold_release_count small
- min trade duration should be ~>= 450 minutes unless loss-release triggers