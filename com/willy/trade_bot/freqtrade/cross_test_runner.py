import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PLAN = REPO_ROOT / "com" / "willy" / "binance" / "freqtrade" / "user_data" / "cross_tests" / "cross_test_plan.json"


@dataclass(frozen=True)
class CmdResult:
    rc: int
    tail: list[str]
    log_path: Path


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _timestamp_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _to_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _to_int(v: Any) -> int | None:
    try:
        if v is None:
            return None
        return int(float(v))
    except Exception:
        return None


def load_plan(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))

    required = ["strategy", "strategy_path", "userdir", "config_files", "timeframe", "train_timerange", "val_timerange"]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"Plan missing required fields: {missing}")
    if not isinstance(data.get("config_files"), list) or not data["config_files"]:
        raise ValueError("config_files must be non-empty list")

    if "stage1_experiments" not in data:
        # Backward compatibility: use experiments as stage1.
        if "experiments" not in data:
            raise ValueError("Plan must provide stage1_experiments or experiments")
        data["stage1_experiments"] = data["experiments"]

    if not isinstance(data["stage1_experiments"], list) or not data["stage1_experiments"]:
        raise ValueError("stage1_experiments must be non-empty list")

    data.setdefault("run_id", f"cross_{_timestamp_id()}")
    data.setdefault("freqtrade_bin", "freqtrade")
    data.setdefault("results_dir", str(Path(data["userdir"]) / "backtest_results"))
    data.setdefault("retry", {"max_attempts": 3, "backoff_seconds": [60, 120, 240]})
    data.setdefault("min_val_trades_for_ranking", 50)
    data.setdefault("hyperopt", {"enabled": False, "epochs": 50, "loss": "SortinoHyperOptLoss", "spaces": ["buy", "sell"], "jobs": 4})
    return data


def write_params_file(params_root: Path, exp_id: str, params_dict: dict[str, Any]) -> Path:
    _ensure_dir(params_root)
    p = params_root / f"{exp_id}.json"
    payload = {"exp_id": exp_id, "params": params_dict}
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def run_cmd(cmd: list[str], env: dict[str, str], log_path: Path) -> CmdResult:
    _ensure_dir(log_path.parent)
    tail: list[str] = []
    tail_len = 120

    with log_path.open("w", encoding="utf-8", errors="replace") as f:
        f.write(f"$ {' '.join(cmd)}\n")
        f.write(f"STRATEGY_PARAM_FILE={env.get('STRATEGY_PARAM_FILE', '')}\n")
        f.flush()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            shell=False,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            f.write(line)
            t = line.rstrip("\n")
            tail.append(t)
            if len(tail) > tail_len:
                tail.pop(0)
        rc = proc.wait()
        f.write(f"\n[exit_code] {rc}\n")
    return CmdResult(rc=rc, tail=tail, log_path=log_path)


def _is_temporary_exchange_error(text: str) -> bool:
    t = text.lower()
    return (
        ("temporaryerror" in t)
        or ("exchangenotavailable" in t)
        or ("exchangeinfo" in t and "not available" in t)
    )


def _list_result_zips(results_dir: Path) -> list[Path]:
    if not results_dir.exists():
        return []
    return sorted([p for p in results_dir.glob("backtest-result-*.zip") if p.is_file()], key=lambda x: x.stat().st_mtime)


def _pick_new_zip(results_dir: Path, before_names: set[str]) -> Path | None:
    zips = _list_result_zips(results_dir)
    if not zips:
        return None
    new = [p for p in zips if p.name not in before_names]
    candidates = new if new else zips
    return max(candidates, key=lambda p: p.stat().st_mtime)


def parse_hyperopt_best_params(hyperopt_results_dir: Path, log_path: Path) -> dict[str, Any]:
    # Minimal parser: currently best-effort only.
    # Keeps workflow resilient even when best params can't be extracted.
    _ = hyperopt_results_dir
    _ = log_path
    return {"params": {}}


def extract_resolved_strategy_info(log_path: Path) -> dict[str, str]:
    info = {"strategy_class": "", "strategy_file": ""}
    if not log_path.exists():
        return info

    text = log_path.read_text(encoding="utf-8", errors="replace")
    patterns = [
        r"Using resolved strategy\s+(\w+)\s+from\s+'([^']+\.py)'",
        r'Using resolved strategy\s+(\w+)\s+from\s+"([^"]+\.py)"',
        r"Found strategy\s+(\w+)\s+in\s+(.+?\.py)",
        r"Loading strategy\s+(\w+).*?(.+?\.py)",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            info["strategy_class"] = (m.group(1) or "").strip()
            info["strategy_file"] = (m.group(2) or "").strip()
            return info
    return info


def run_hyperopt(plan: dict[str, Any], run_dirs: dict[str, Path], exp_id: str, env: dict[str, str]) -> tuple[dict[str, Any], CmdResult]:
    hp = plan.get("hyperopt", {})
    cmd = [
        str(plan["freqtrade_bin"]),
        "hyperopt",
        "--strategy",
        str(plan["strategy"]),
        "--strategy-path",
        str(plan["strategy_path"]),
        "--userdir",
        str(plan["userdir"]),
        "--timerange",
        str(plan["train_timerange"]),
        "--timeframe",
        str(plan["timeframe"]),
        "--hyperopt-loss",
        str(hp.get("loss", "SortinoHyperOptLoss")),
        "--epochs",
        str(hp.get("epochs", 50)),
        "-j",
        str(hp.get("jobs", 4)),
    ]
    spaces = hp.get("spaces") or []
    if spaces:
        cmd.extend(["--spaces", *[str(s) for s in spaces]])
    for c in plan["config_files"]:
        cmd.extend(["--config", str(c)])

    log_path = run_dirs["logs"] / f"{exp_id}_hyperopt.log"
    res = run_cmd(cmd, env, log_path)
    best = parse_hyperopt_best_params(Path(plan["userdir"]) / "hyperopt_results", log_path)
    return best, res


def run_backtest(
    plan: dict[str, Any],
    run_dirs: dict[str, Path],
    exp_id: str,
    split_name: str,
    timerange: str,
    env: dict[str, str],
    extra_args: list[str] | None = None,
) -> tuple[Path | None, CmdResult]:
    results_dir = Path(plan["results_dir"])
    before = {p.name for p in _list_result_zips(results_dir)}

    cmd = [
        str(plan["freqtrade_bin"]),
        "backtesting",
        "--strategy",
        str(plan["strategy"]),
        "--strategy-path",
        str(plan["strategy_path"]),
        "--userdir",
        str(plan["userdir"]),
        "--timerange",
        str(timerange),
        "--timeframe",
        str(plan["timeframe"]),
        "--export",
        "trades",
        "--cache",
        "none",
    ]
    for c in plan["config_files"]:
        cmd.extend(["--config", str(c)])
    if extra_args:
        cmd.extend(extra_args)

    retry_cfg = plan.get("retry", {}) or {}
    max_attempts = int(retry_cfg.get("max_attempts", 3))
    backoff = retry_cfg.get("backoff_seconds", [60, 120, 240])
    if not isinstance(backoff, list) or not backoff:
        backoff = [60, 120, 240]

    last_res: CmdResult | None = None
    for attempt in range(1, max_attempts + 1):
        suffix = f"_attempt{attempt}" if max_attempts > 1 else ""
        log_path = run_dirs["logs"] / f"{exp_id}_{split_name}{suffix}.log"
        res = run_cmd(cmd, env, log_path)
        last_res = res
        if res.rc == 0:
            src_zip = _pick_new_zip(results_dir, before)
            if src_zip is None:
                return None, res
            dst = run_dirs["results"] / f"{exp_id}_{split_name}.zip"
            shutil.copy2(src_zip, dst)
            return dst, res

        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        if attempt < max_attempts and _is_temporary_exchange_error(log_text):
            delay = int(backoff[min(attempt - 1, len(backoff) - 1)])
            time.sleep(delay)
            continue
        break

    assert last_res is not None
    return None, last_res


def summarize_backtest(zip_path: Path, strategy_name: str) -> dict[str, Any]:
    out: dict[str, Any] = {"zip": str(zip_path), "status": "ok"}
    if not zip_path.exists():
        out["status"] = "missing_zip"
        return out

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = [
            n
            for n in zf.namelist()
            if n.endswith(".json")
            and "_config" not in n
            and ".meta" not in n
            and not n.endswith("summary.json")
        ]
        if not names:
            out["status"] = "missing_result_json"
            return out
        result_name = sorted(names, key=lambda x: (x.count("/"), x))[-1]
        data = json.loads(zf.read(result_name).decode("utf-8", errors="replace"))

    s = data.get("strategy", {}).get(strategy_name, {})
    if not isinstance(s, dict):
        out["status"] = "missing_strategy_data"
        return out

    out.update(
        {
            "trades": s.get("total_trades"),
            "profit_total_abs": s.get("profit_total_abs"),
            "profit_total_pct": (_to_float(s.get("profit_total")) or 0.0) * 100,
            "profit_factor": s.get("profit_factor"),
            "max_drawdown": s.get("max_drawdown_account"),
            "winrate": s.get("winrate"),
            "sharpe": s.get("sharpe"),
            "sortino": s.get("sortino"),
            "calmar": s.get("calmar"),
            "avg_duration": s.get("holding_avg_s"),
        }
    )
    return out


def _rank_tuple_for_val(row: dict[str, Any]) -> tuple[float, float, float, float]:
    pf_raw = _to_float(row.get("val_pf"))
    pnl_raw = _to_float(row.get("val_pnl_pct"))
    dd_raw = _to_float(row.get("val_dd"))
    trades_raw = _to_float(row.get("val_trades"))

    pf = pf_raw if pf_raw is not None else float("-inf")
    pnl = pnl_raw if pnl_raw is not None else float("-inf")
    dd_key = -dd_raw if dd_raw is not None else float("-inf")  # asc drawdown => larger is better after negation
    trades = trades_raw if trades_raw is not None else float("-inf")
    return pf, pnl, dd_key, trades


def _rows_to_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    _ensure_dir(path.parent)
    fields = [
        "exp_id",
        "stage",
        "status",
        "params_file",
        "train_trades",
        "train_pf",
        "train_pnl_pct",
        "train_dd",
        "train_winrate",
        "val_trades",
        "val_pf",
        "val_pnl_pct",
        "val_dd",
        "val_winrate",
        "val_rank_key",
        "train_zip",
        "val_zip",
        "train_log",
        "val_log",
        "train_strategy_class",
        "train_strategy_file",
        "val_strategy_class",
        "val_strategy_file",
        "overrides",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})


def _rows_to_md(path: Path, rows: list[dict[str, Any]]) -> None:
    _ensure_dir(path.parent)
    cols = ["exp_id", "stage", "status", "val_pf", "val_pnl_pct", "val_dd", "val_trades", "params_file"]
    lines = ["# Cross Test Summary", "", "| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    path.write_text("\n".join(lines), encoding="utf-8")


def _run_one_experiment(
    plan: dict[str, Any],
    run_dirs: dict[str, Path],
    base_env: dict[str, str],
    exp: dict[str, Any],
    stage: int,
) -> dict[str, Any]:
    exp_id = str(exp["id"])
    overrides = dict(exp.get("overrides") or {})
    params_file = write_params_file(run_dirs["params_root"], exp_id, overrides)
    env = dict(base_env)
    env["STRATEGY_PARAM_FILE"] = str(params_file)

    row: dict[str, Any] = {
        "exp_id": exp_id,
        "stage": stage,
        "status": "ok",
        "params_file": str(params_file),
        "overrides": json.dumps(overrides, ensure_ascii=False),
        "train_strategy_class": "",
        "train_strategy_file": "",
        "val_strategy_class": "",
        "val_strategy_file": "",
    }

    if bool((plan.get("hyperopt") or {}).get("enabled", False)):
        best, hres = run_hyperopt(plan, run_dirs, exp_id, env)
        if hres.rc != 0:
            row["status"] = "hyperopt_failed"
            return row
        best_params = best.get("params", {})
        if isinstance(best_params, dict) and best_params:
            merged = dict(overrides)
            merged.update(best_params)
            params_file = write_params_file(run_dirs["params_root"], exp_id, merged)
            env["STRATEGY_PARAM_FILE"] = str(params_file)
            row["params_file"] = str(params_file)

    train_zip, train_res = run_backtest(
        plan=plan,
        run_dirs=run_dirs,
        exp_id=exp_id,
        split_name="train",
        timerange=str(plan["train_timerange"]),
        env=env,
        extra_args=[str(x) for x in (exp.get("extra_backtest_args") or [])],
    )
    row["train_log"] = str(train_res.log_path)
    train_info = extract_resolved_strategy_info(train_res.log_path)
    row["train_strategy_class"] = train_info.get("strategy_class", "")
    row["train_strategy_file"] = train_info.get("strategy_file", "")
    if train_res.rc != 0 or train_zip is None:
        row["status"] = "train_failed"
        return row

    train_sum = summarize_backtest(train_zip, str(plan["strategy"]))
    row["train_trades"] = train_sum.get("trades")
    row["train_pf"] = train_sum.get("profit_factor")
    row["train_pnl_pct"] = train_sum.get("profit_total_pct")
    row["train_dd"] = train_sum.get("max_drawdown")
    row["train_winrate"] = train_sum.get("winrate")
    row["train_zip"] = str(train_zip)

    val_zip, val_res = run_backtest(
        plan=plan,
        run_dirs=run_dirs,
        exp_id=exp_id,
        split_name="val",
        timerange=str(plan["val_timerange"]),
        env=env,
        extra_args=[str(x) for x in (exp.get("extra_backtest_args") or [])],
    )
    row["val_log"] = str(val_res.log_path)
    val_info = extract_resolved_strategy_info(val_res.log_path)
    row["val_strategy_class"] = val_info.get("strategy_class", "")
    row["val_strategy_file"] = val_info.get("strategy_file", "")
    if val_res.rc != 0 or val_zip is None:
        row["status"] = "val_failed"
        return row

    val_sum = summarize_backtest(val_zip, str(plan["strategy"]))
    row["val_trades"] = val_sum.get("trades")
    row["val_pf"] = val_sum.get("profit_factor")
    row["val_pnl_pct"] = val_sum.get("profit_total_pct")
    row["val_dd"] = val_sum.get("max_drawdown")
    row["val_winrate"] = val_sum.get("winrate")
    row["val_zip"] = str(val_zip)
    row["val_rank_key"] = str(_rank_tuple_for_val(row))
    return row


def _build_stage2_experiments(stage1_ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    top2 = stage1_ranked[:2]
    if len(top2) < 2:
        return []

    stage2: list[dict[str, Any]] = []
    base_ids = ["E15", "E16", "E17", "E18"]
    idx = 0
    for top in top2:
        top_overrides = json.loads(top.get("overrides") or "{}")
        # avoid_spike
        o1 = dict(top_overrides)
        o1.update(
            {
                "use_volume_filter": True,
                "volume_filter_mode": "avoid_spike",
                "vol_window": 48,
                "vol_ratio_max": 1.2,
            }
        )
        stage2.append({"id": base_ids[idx], "overrides": o1})
        idx += 1

        # band
        o2 = dict(top_overrides)
        o2.update(
            {
                "use_volume_filter": True,
                "volume_filter_mode": "band",
                "vol_window": 48,
                "vol_ratio_low": 0.8,
                "vol_ratio_high": 1.3,
            }
        )
        stage2.append({"id": base_ids[idx], "overrides": o2})
        idx += 1
    return stage2


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross test runner (stage1 + stage2)")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    args = parser.parse_args()

    plan_path = Path(args.plan).resolve()
    plan = load_plan(plan_path)

    run_id = str(plan["run_id"])
    userdir = Path(plan["userdir"]).resolve()
    run_root = userdir / "cross_tests" / run_id
    run_dirs = {
        "root": run_root,
        "plans": run_root / "plans",
        "logs": run_root / "logs",
        "results": run_root / "results",
        "params_root": userdir / "strategy_params" / run_id,
    }
    for d in run_dirs.values():
        _ensure_dir(d)

    shutil.copy2(plan_path, run_dirs["plans"] / plan_path.name)
    (run_dirs["plans"] / "resolved_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

    base_env = dict(os.environ)
    all_rows: list[dict[str, Any]] = []

    # Stage1
    stage1_rows: list[dict[str, Any]] = []
    for exp in plan["stage1_experiments"]:
        stage1_rows.append(_run_one_experiment(plan, run_dirs, base_env, exp, stage=1))
    all_rows.extend(stage1_rows)

    min_val_trades = int(plan.get("min_val_trades_for_ranking", 50))
    ok_stage1 = [r for r in stage1_rows if r.get("status") == "ok"]
    ranked_pool = [r for r in ok_stage1 if (_to_int(r.get("val_trades")) or 0) >= min_val_trades]
    ok_stage1_sorted = sorted(ranked_pool, key=_rank_tuple_for_val, reverse=True)

    # Stage2 (auto)
    stage2_exps: list[dict[str, Any]] = []
    if len(ok_stage1_sorted) < 2:
        print(
            f"[warn] Stage2 skipped: only {len(ok_stage1_sorted)} stage1 candidates meet "
            f"min_val_trades_for_ranking={min_val_trades}."
        )
    else:
        stage2_exps = _build_stage2_experiments(ok_stage1_sorted)
    stage2_rows: list[dict[str, Any]] = []
    for exp in stage2_exps:
        stage2_rows.append(_run_one_experiment(plan, run_dirs, base_env, exp, stage=2))
    all_rows.extend(stage2_rows)

    # Final ranking by required tuple
    ranked = sorted(
        all_rows,
        key=lambda r: _rank_tuple_for_val(r) if r.get("status") == "ok" else (float("-inf"), float("-inf"), float("-inf"), float("-inf")),
        reverse=True,
    )

    summary_csv = run_root / "summary.csv"
    summary_md = run_root / "summary.md"
    _rows_to_csv(summary_csv, ranked)
    _rows_to_md(summary_md, ranked)

    print("=" * 80)
    print(f"Run ID: {run_id}")
    print(f"Summary CSV: {summary_csv}")
    print(f"Summary MD : {summary_md}")
    print(f"Results Dir: {run_dirs['results']}")
    print("=" * 80)
    for r in ranked[:8]:
        print(
            f"{r.get('exp_id')} stage={r.get('stage')} status={r.get('status')} "
            f"val_pf={r.get('val_pf')} val_pnl={r.get('val_pnl_pct')} val_dd={r.get('val_dd')} val_trades={r.get('val_trades')}"
        )


if __name__ == "__main__":
    main()
