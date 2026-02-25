# Codex Request: Fix and Guarantee obs_close_gt_ma7_count_since_dc

We already have a working Freqtrade strategy (AMRS3_13Strategy).
Now we need to CORRECT and HARDEN the observation signal:

Goal:
Ensure `obs_close_gt_ma7_count_since_dc` correctly counts
"how many times close > MA7 AFTER each MA7 death cross MA25"
and is safe for statistical grouping analysis.

The observation MUST:
- Reset after each MA7 cross BELOW MA25
- NOT count candles before the first death cross
- Be exported in signals (--export signals)

---

## Required Indicator Logic

Inside populate_indicators:

1) Define death cross:
   MA7 crosses BELOW MA25

   dc_event = (
       (ma7 < ma25) &
       (ma7.shift(1) >= ma25.shift(1))
   )

2) Store boolean column:

   dataframe["obs_dc_ma7_below_ma25"]

3) Create segment id:

   dataframe["obs_dc_id"] = dataframe["obs_dc_ma7_below_ma25"].cumsum()

4) Only count AFTER first death cross:

   post_dc = dataframe["obs_dc_id"] > 0

5) Define close_gt_ma7:

   dataframe["obs_close_gt_ma7"] = close > ma7

6) Count occurrences per segment:

   dataframe["obs_close_gt_ma7_count_since_dc"] = (
       dataframe["obs_close_gt_ma7"]
       .where(post_dc, False)
       .astype(int)
       .groupby(dataframe["obs_dc_id"])
       .cumsum()
   )

Important:
- Before first death cross, count must remain 0
- After each new death cross, count resets to 0

---

## Do NOT change trading logic
Entry / Exit / Hold / Loss-release must remain exactly as before.

---

## Acceptance Criteria

After running:

freqtrade backtesting --strategy AMRS3_13Strategy --export signals

signal_context.csv must contain:

- obs_dc_ma7_below_ma25
- obs_dc_id
- obs_close_gt_ma7
- obs_close_gt_ma7_count_since_dc

Manual check:
- Before first death cross → count = 0
- After each new death cross → count resets to 0
- Count increments only when close > MA7