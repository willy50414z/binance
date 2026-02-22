import json
import os
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from typing import Any

import pyperclip

# Allow running this file directly (python com/willy/.../freqtrade_executor.py)
# while still supporting absolute imports like `com.willy...`.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

RESULTS_DIR = r"E:\code\binance\com\willy\binance\freqtrade\user_data\backtest_results"
USERDIR = r"E:\code\binance\com\willy\binance\freqtrade\user_data"
STRATEGY_PATH = r"E:\code\binance\com\willy\binance\freqtrade\strategy\AMRS(ATR-Driven Mean Reversion Short"
TIMERANGE = "20240101-20261231"
CONFIG_PATH = r"E:\code\binance\com\willy\binance\freqtrade\config.json"

MODE = "backtesting"  # Options: "backtesting" or "hyperopt"
HYPEROPT_EPOCHS = 100

# When running backtesting, run hyperopt once first.
RUN_HYPEROPT_BEFORE_BACKTESTING = False

# Multi-strategy support (kept minimal on purpose).
STRATEGIES = [
    "AMRS3_7Strategy",
]

# Backtesting CLI supports exporting only one artifact at a time (trades OR signals) in your current version.
EXPORT_TRADES = False
EXPORT_SIGNALS = True

# Output reports next to backtest results.
REPORTS_DIR = os.path.join(RESULTS_DIR, "reports")
CHARTS_DIR = os.path.join(REPORTS_DIR, "charts")
EXPORT_TRADE_CHART = True

LAST_RESULT_FILE = os.path.join(RESULTS_DIR, ".last_result.json")


@dataclass(frozen=True)
class RunArtifacts:
    stem: str
    json_path: str | None
    signals_path: str | None
    meta_path: str | None
    zip_path: str | None
    extracted_dir: str | None


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _print_cmd(cmd: list[str]) -> None:
    # Keep a readable representation without relying on shell quoting.
    print("Executing:", " ".join(cmd))


def _run_cmd(cmd: list[str], note: str | None = None, cwd: str | None = None) -> tuple[int, str, str]:
    _print_cmd(cmd)
    if note:
        print(note)

    try:
        cp = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=False,
            encoding="utf-8",
            errors="replace",
        )
        return cp.returncode, cp.stdout or "", cp.stderr or ""
    except FileNotFoundError:
        # Fallback for environments where "freqtrade" is a shell shim (rare).
        cmd_str = subprocess.list2cmdline(cmd)
        cp = subprocess.run(
            cmd_str,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=True,
            encoding="utf-8",
            errors="replace",
        )
        return cp.returncode, cp.stdout or "", cp.stderr or ""


def _list_result_zips() -> list[str]:
    try:
        return [
            n
            for n in os.listdir(RESULTS_DIR)
            if n.startswith("backtest-result-") and n.endswith(".zip")
        ]
    except Exception:
        return []


def _pick_new_zip(before: set[str]) -> str | None:
    after = set(_list_result_zips())
    new = list(after - before)
    candidates = new or list(after)
    if not candidates:
        return None
    return max(candidates, key=lambda n: os.path.getmtime(os.path.join(RESULTS_DIR, n)))


def run_backtesting(strategy_name: str, export: str) -> tuple[int, str, str, str | None]:
    if export not in {"none", "trades", "signals"}:
        raise ValueError(f"Invalid export='{export}', expected one of: none/trades/signals")

    _ensure_dir(RESULTS_DIR)
    before = set(_list_result_zips())

    cmd = [
        "freqtrade",
        "backtesting",
        "--config",
        CONFIG_PATH,
        "--strategy",
        strategy_name,
        "--strategy-path",
        STRATEGY_PATH,
        "--userdir",
        USERDIR,
        "--timerange",
        TIMERANGE,
        "--export",
        export,
        "--cache",
        "none",
    ]
    ret, stdout, stderr = _run_cmd(cmd)
    zip_name = _pick_new_zip(before) if ret == 0 else None
    stem = os.path.splitext(zip_name)[0] if zip_name else None
    return ret, stdout, stderr, stem


def run_hyperopt(strategy_name: str) -> tuple[int, str, str]:
    cmd = [
        "freqtrade",
        "hyperopt",
        "--config",
        CONFIG_PATH,
        "--strategy",
        strategy_name,
        "--strategy-path",
        STRATEGY_PATH,
        "--userdir",
        USERDIR,
        "--timerange",
        TIMERANGE,
        "-e",
        str(HYPEROPT_EPOCHS),
        "--hyperopt-loss",
        "SortinoHyperOptLoss",
        "-j",
        "4",
    ]
    return _run_cmd(cmd, note="Note: Hyperopt may take several minutes...")


def _save_execution_result(strategy_name: str, stem: str) -> None:
    data = {
        "strategy_name": strategy_name,
        "stem": stem,
        "timerange": TIMERANGE,
        "latest_backtest": f"{stem}.zip",
    }
    with open(LAST_RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def main() -> None:
    _ensure_dir(RESULTS_DIR)
    _ensure_dir(REPORTS_DIR)
    _ensure_dir(CHARTS_DIR)

    print("=" * 60)
    print(f"Freqtrade {MODE.title()} Executor")
    print(f"Timerange: {TIMERANGE}")
    if MODE == "hyperopt":
        print(f"Epochs: {HYPEROPT_EPOCHS}")
    print("=" * 60)

    for strategy_name in STRATEGIES:
        print("\n" + "-" * 60)
        print(f"Strategy: {strategy_name}")
        print("-" * 60)

        if MODE == "hyperopt":
            ret, stdout, stderr = run_hyperopt(strategy_name)
            if ret != 0:
                report = (
                    f"Hyperopt Error (exit code: {ret})\n\n"
                    f"Output:\n{stdout}\n\nSTDERR:\n{stderr}"
                )
                pyperclip.copy(report)
                print(report)
                return
            pyperclip.copy(stdout)
            print("Hyperopt completed. Output copied to clipboard.")
            continue

        # backtesting mode
        stem: str | None = None
        ret = 0

        if EXPORT_TRADES:
            ret, out, err, run_stem = run_backtesting(strategy_name, export="trades")
            if run_stem:
                stem = run_stem
            if ret != 0:
                report = (
                    f"Backtesting (trades) Error (exit code: {ret})\n\n"
                    f"Output:\n{out}\n\nSTDERR:\n{err}"
                )
                pyperclip.copy(report)
                print(report)
                return

        if EXPORT_SIGNALS:
            ret, out, err, run_stem = run_backtesting(strategy_name, export="signals")
            if run_stem:
                stem = run_stem
            if ret != 0:
                report = (
                    f"Backtesting (signals) Error (exit code: {ret})\n\n"
                    f"Output:\n{out}\n\nSTDERR:\n{err}"
                )
                pyperclip.copy(report)
                print(report)
                return

        if not stem:
            report = "Backtesting completed, but could not resolve output artifacts (no new .zip found)."
            pyperclip.copy(report)
            print(report)
            return

        _save_execution_result(strategy_name, stem)
        print(f"\nBacktesting completed. Stem: {stem}")
        print(f"Run analyze_backtest_result.py to analyze the results.")


if __name__ == "__main__":
    main()
