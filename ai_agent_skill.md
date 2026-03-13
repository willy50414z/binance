# AI Agent Skill

Shared project instructions for AI agents working in this repository.

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
- Save created or modified files as UTF-8 without BOM when feasible to avoid Windows encoding issues.

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

### Strategy Workflow Skill

- Each strategy should have its own folder under `com/willy/trade_bot/ml/`.
- User-managed discussion summaries should live under that strategy folder's `sessions/`.
- Training outputs should be produced by code under that strategy folder's `generated/`.
- Do not create extra review or session markdown files unless the user explicitly asks for one.

### Documentation Skill

- Keep `Financial ML step by step.md` aligned with the actual code path, not an idealized design.
- If a workflow changes, update the user-specified strategy-local docs in the same task when feasible.
- If asked to review code and export suggested changes to a markdown file, read `knowledge-base/skills/code-review-md-export/SKILL.md` first and follow that workflow.
- When code and markdown disagree, use the code as the source of truth and update the markdown accordingly.

### ML Trading Strategy Skill

- When developing or modifying ML training scripts or trading strategies, also review `knowledge-base/skills/ml-trading-strategy/SKILL.md` when that workflow is relevant.
- Strictly check for look-ahead bias, weak baselines, and unrealistic backtest assumptions.

### Plan Consensus Review Skill

- Before finalizing a substantial execution plan, draft a preliminary plan first.
- Then use `com/willy/trade_bot/service/llm_svc.py` to ask another LLM to review that plan from the most relevant expert perspective for the task.
- Pick the reviewer angle based on the work type, for example:
    - ML or trading logic: financial ML or quantitative trading expert
    - software design or refactor: senior software architect
    - data pipeline or validation flow: data engineering or ML platform expert
    - risk, correctness, or process control: reviewer focused on failure modes and missing safeguards
- Ask the external LLM to check whether the draft plan is missing steps, has weak assumptions, introduces leakage or validation risk, or should be reordered.
- Integrate the external review with the local analysis before producing the final execution plan.
- If the external review conflicts with local judgment, explicitly resolve the disagreement and explain which recommendation is adopted.
- Follow `knowledge-base/skills/ml-consensus-review/SKILL.md` for the detailed workflow when plan consensus review is needed.

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

Add more project-specific skills here when needed, for example:

- feature engineering conventions
- backtest evaluation checklist
- model artifact naming/versioning rules
- exchange data quality checks
- deployment or inference constraints
