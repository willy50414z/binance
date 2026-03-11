# AGENTS.md

## Project Overview

- Repo: `bianace`
- Focus: Binance trading, technical indicators, and ML training workflows
- Main code areas:
    - `com/willy/trade_bot/`
    - `com/willy/trade_bot/ml/`
    - `knowledge-base/`

## Working Rules

- Read existing code before changing behavior.
- Prefer minimal, targeted edits over broad refactors.
- Preserve time-series correctness and avoid look-ahead bias.
- Do not change model assumptions silently; document any ML logic change.
- When updating training logic, also review related markdown docs in `com/willy/trade_bot/ml/`.

## Project Skills

Use these project-specific habits by default when working in this repo.

### ML Workflow Skill

- Treat every model change as both an engineering change and a research change.
- Check data leakage risk first:
    - target construction
    - lagging
    - normalization fit scope
    - multi-timeframe joins
    - validation split boundaries
- Prefer time-series split or walk-forward style validation over random split.
- Do not judge model quality by classification metrics alone; check trading impact assumptions.
- When editing `binance_tech_idx_model_trainer.py`, also review:
    - target labeling logic
    - calibration logic
    - threshold selection logic
    - artifact output names

### Documentation Skill

- Keep `Financial ML step by step.md` aligned with the actual code path, not an idealized design.
- Record important findings, risks, and follow-up items in `session.md`.
- If a workflow changes, update docs in the same task when feasible.
- If asked to review code and export suggested changes to a markdown file, read `knowledge-base/skills/code-review-md-export/SKILL.md` first and follow that workflow.
- Strategy workflow:
    - each strategy has its own folder under `com/willy/trade_bot/ml/`
    - user-managed discussion summaries live under that strategy folder's `sessions/`
    - training outputs should be produced by code under that strategy folder's `generated/`
    - do not create extra review/session markdown files unless the user explicitly asks for one

### Trading Domain Skill

- Assume transaction cost, slippage, and regime shift matter unless explicitly excluded.
- Be conservative about claims of model edge.
- Flag anything that can inflate backtest or validation results.

## Preferred Output Style

- Be concise and direct.
- Present ML review results as:
    1. leakage or correctness risk
    2. validation risk
    3. trading applicability risk
    4. concrete next actions

## Safe Defaults

- Prefer reproducible parameters over `now()`-driven experiments when adding new training flows.
- Prefer UTF-8 safe logs and avoid console output that may break on Windows encodings.
- If a change affects saved model artifacts, call that out explicitly.

## Notes For Future Expansion

Add more project-specific skills here, for example:

- feature engineering conventions
- backtest evaluation checklist
- model artifact naming/versioning rules
- exchange data quality checks
- deployment or inference constraints
