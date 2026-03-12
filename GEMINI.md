# GEMINI.md

This file contains project-specific instructions and rules for Gemini CLI when working in this repository. These mandates take absolute precedence over general workflows.

## Project Overview

- **Repository:** `bianace`
- **Focus:** Binance trading bot, technical indicator calculation, and ML training workflows.
- **Main Code Areas:**
    - `com/willy/trade_bot/`: Core trading bot logic and services.
    - `com/willy/trade_bot/ml/`: Machine learning training, prediction, and validation.
    - `knowledge-base/`: Documentation and specialized skills.

## Working Rules

- **Research First:** Read existing code and understand the context before changing any behavior.
- **Surgical Edits:** Prefer minimal, targeted changes over broad refactors.
- **Data Integrity:** Preserve time-series correctness and strictly avoid look-ahead bias in all trading and ML logic.
- **Documentation:** Do not change model assumptions silently; document any ML logic changes clearly.
- **Sync Docs:** When updating training logic, also review related markdown documentation in `com/willy/trade_bot/ml/`.
- **UTF-8 Safety:** Prefer UTF-8 safe logs and avoid console output that may break on Windows encodings.

## Project Skills

### ML Workflow Skill
- Treat every model change as both an engineering change and a research change.
- **Data Leakage Check:** Always check for leakage risks (target construction, lagging, normalization fit scope, multi-timeframe joins, validation split boundaries).
- **Validation:** Prefer time-series split or walk-forward validation over random splits.
- **Metrics:** Do not judge model quality by classification metrics alone; check trading impact assumptions.
- **Trainer Updates:** When editing `binance_tech_idx_model_trainer.py`, review target labeling, calibration, threshold selection, and artifact names.

### Local Review Workflow Skill
- **Location:** `knowledge-base/skills/code-review-md-export/SKILL.md`
- **Trigger:** If asked to review code and update a markdown review/spec file, read this skill first and follow its workflow.
- **Source of Truth:** When code and markdown disagree, use the code as the source of truth and update the markdown accordingly.
- **Strategy Layout:** Assume each strategy has its own folder, user-managed discussion notes live in its `sessions/` directory, and training outputs are produced by code in its `generated/` directory.
- **Default Behavior:** Do not create extra review/session markdown files unless the user explicitly asks for one.

### Trading Domain Skill
- **Real-world Constraints:** Assume transaction costs, slippage, and regime shifts matter unless explicitly excluded.
- **Edge Claims:** Be conservative about claims of model edge.
- **Flagging:** Explicitly flag anything that could potentially inflate backtest or validation results.

### Documentation Skill
- **Alignment:** Keep `Financial ML step by step.md` aligned with the actual code path.
- **Workflow Updates:** If a workflow changes, update the user-specified strategy-local documentation in the same task when asked.
- **No Default Export:** Do not create extra review or session markdown files unless the user explicitly asks for that file-level update.

## Preferred Output Style

- Be concise and direct.
- Present ML review results as:
    1. Leakage or correctness risk
    2. Validation risk
    3. Trading applicability risk
    4. Concrete next actions
