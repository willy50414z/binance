# Execution Plan: Backtest Stats Upgrade (focus: find strategy core defects)

## Goal

Produce enough diagnostics to pinpoint WHY expectancy is negative despite high winrate,
and identify the losing trade cluster(s) (esp. ma25_defense).

Success Criteria:

- signal_context.csv is NOT empty
- regime_bins.csv is NOT empty
- trades can be segmented by entry context (enter_tag + indicator snapshot)
- we can explain: "which entry conditions → end up in ma25_defense"

---

## 0) Current Findings (from latest zip)

- trades: 509
- winrate: ~70.5%
- expectancy: -0.10% (negative)
- avg_win_pct: +0.58%
- avg_loss_pct: -1.74%
- main loss driver: exit_reason = ma25_defense
    - 130 trades, winrate=0%, mean_pct≈-1.98%, sum_abs≈-4707
- atr_trailing_exit is strongly positive
    - 185 trades, winrate=100%, mean_pct≈+0.98%, sum_abs≈+3292

---

## 1) Fix Data Join: signals.pkl ↔ trades

Problem:

- validation.json shows join_integrity: entry_event_trade_count=0, exit_event_trade_count=0
- signal_context.csv and regime_bins.csv are empty

Action:

1. Load signals.pkl and normalize schema:
    - ensure it has: pair, candle_time (or date), signal_type (enter/exit), and optionally enter_tag/exit_tag
2. Normalize trades.csv dates:
    - open_date, close_date -> timezone-aware or consistent timezone (UTC or local)
3. Join strategy:
    - Join Entry:
        - trades.open_date rounded/floored to candle_time (timeframe) AND pair
    - Join Exit:
        - trades.close_date rounded/floored to candle_time (timeframe) AND pair
4. Add join diagnostics:
    - join_rate_entry = matched_entry_trades / total_trades
    - join_rate_exit = matched_exit_trades / total_trades
    - dump unmatched samples (top 20) for debugging

Output:

- join_diagnostics.json
- signal_context.csv (non-empty)
- unmatched_entry_trades.csv
- unmatched_exit_trades.csv

Acceptance:

- join_rate_entry >= 0.95
- join_rate_exit  >= 0.95
- signal_context.csv rows >= total_trades (or close)

---

## 2) Add Trade "Entry Snapshot" Features (core defect hunting)

Why:

- We must know what the market/indicator state was at entry for losing clusters.

Action:
For each trade, attach a snapshot (from candle at/just before entry):

- price features:
    - close, high, low, volume
    - ATR (same as strategy uses)
    - returns: 1/3/6/12 candles
- trend / mean reversion features:
    - MA25 slope (delta), distance_to_MA25 (%)
    - RSI / Stoch / whatever strategy uses (exact columns)
- volatility features:
    - ATR%, BB width, etc (if available)
- tags:
    - enter_tag (MUST be set in strategy)
    - exit_reason (already present)

Output:

- trade_features.csv (1 row per trade, wide table)

Acceptance:

- trade_features.csv rows == total_trades
- enter_tag coverage >= 0.95 (non-null)

---

## 3) Add Path-based Risk Metrics: MAE/MFE and Excursion Timing

Why:

- Negative expectancy often comes from tail losses or late defense exits.
- Need to know if ma25_defense happens after large adverse excursion.

Action:
For each trade, use candle path between open_date and close_date:

- MFE_pct: max favorable excursion (%)
- MAE_pct: max adverse excursion (%)
- time_to_MFE, time_to_MAE (minutes or candles)
- max_drawdown_during_trade_pct

Output:

- trade_excursions.csv
- merge into trade_features.csv

Acceptance:

- coverage >= 0.98 (some trades may miss due to data gaps, but should be minimal)

---

## 4) Regime Labeling (market conditions buckets)

Why:

- We need to know if ma25_defense cluster happens in:
    - trending down markets
    - high volatility chop
    - low vol drift, etc.

Action:
Create regime labels per candle (then map to trade entry candle):

- Trend regime:
    - MA25 slope bucket: strong_down / mild_down / flat / mild_up / strong_up
- Vol regime:
    - ATR% bucket: low / mid / high (quantiles)
- Optional:
    - volume regime: low / mid / high

Output:

- candle_regimes.csv
- regime_bins.csv (aggregate by regime + exit_reason)

Acceptance:

- regime_bins.csv non-empty
- we can answer: "ma25_defense rate by regime"

---

## 5) Cluster Report: What Causes ma25_defense?

Action:
Generate a focused report comparing:
Group A: exit_reason == ma25_defense
Group B: exit_reason in {atr_trailing_exit, roi, trailing_stop_loss}

For each feature in trade_features:

- mean/median difference
- effect size (simple z-score or percentile diff)
- top 10 separating features

Output:

- ma25_defense_rootcause.md
- ma25_defense_feature_diff.csv

Acceptance:

- report includes actionable rule candidates, e.g.:
    - "Avoid entries where distance_to_MA25 < X and MA25_slope < 0"
    - "Tighten defense stop from -2% to -Y% when ATR% > Z"
    - "Disable ma25_defense and replace with ATR-based hard stop"

---

## 6) Minimal Strategy Instrumentation (to fill missing tags)

Action:
Update strategy to set tags:

- enter_tag:
    - include signal name + key thresholds
    - example: "mr_entry_rsi<30_atrHigh"
- exit_tag (optional):
    - include which exit logic fired and key value

Output:

- tags reflected in next backtest exports

Acceptance:

- entry_exit_reason.csv enter_tag not NaN

---

## Deliverables Checklist (what to export each run)

Must-have:

- trades.csv
- daily_pnl.csv
- equity_curve.csv
- pair_breakdown.csv
- cost_impact.csv
- time_breakdown.csv
- trade_features.csv          (NEW)
- trade_excursions.csv        (NEW)
- regime_bins.csv             (FIXED, non-empty)
- signal_context.csv          (FIXED, non-empty)
- join_diagnostics.json       (NEW)
- ma25_defense_rootcause.md   (NEW)

---

## Next Improvement Targets (based on current stats)

Priority 1:

- Reduce/avoid ma25_defense trades (currently 130 trades, 0% winrate)
  Priority 2:
- Improve risk-reward:
    - either increase avg_win_pct OR reduce avg_loss_pct
      Priority 3:
- Verify fee/slippage assumptions:
    - cost_impact.csv should quantify if fees push borderline winners to losers