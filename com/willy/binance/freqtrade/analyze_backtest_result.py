import json
import os
import shutil
import csv
import sys
import zipfile
import math
import statistics
import hashlib
import subprocess
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pyperclip

# Allow running this file directly
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

RESULTS_DIR = r"E:\code\binance\com\willy\binance\freqtrade\user_data\backtest_results"
USERDIR = r"E:\code\binance\com\willy\binance\freqtrade\user_data"
STRATEGY_PATH = r"E:\code\binance\com\willy\binance\freqtrade\strategy\AMRS(ATR-Driven Mean Reversion Short"
TIMERANGE = "20240101-20261231"

REPORTS_DIR = os.path.join(RESULTS_DIR, "reports")
CHARTS_DIR = os.path.join(REPORTS_DIR, "charts")
EXPORT_TRADE_CHART = False

LAST_RESULT_FILE = os.path.join(RESULTS_DIR, ".last_result.json")


@dataclass(frozen=True)
class RunArtifacts:
    stem: str
    json_path: str | None
    signals_path: str | None
    rejected_path: str | None
    market_change_path: str | None
    config_path: str | None
    meta_path: str | None
    zip_path: str | None
    extracted_dir: str | None


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _safe_read_json(path: str) -> dict[str, Any] | None:
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return json.load(f)


def _maybe_extract_zip(zip_path: str, extract_dir: str) -> None:
    if not os.path.exists(zip_path):
        return
    _ensure_dir(extract_dir)
    with zipfile.ZipFile(zip_path, "r") as zf:
        # Only extract the small artifacts we actually need and skip large/unhelpful files
        # (e.g. freqtrade logs) that can bloat the reports folder.
        stem = os.path.splitext(os.path.basename(zip_path))[0]
        allow = {
            f"{stem}.json",
            f"{stem}.meta.json",
            f"{stem}_config.json",
            f"{stem}_signals.json",
            f"{stem}_signals.pkl",
            f"{stem}_rejected.pkl",
            f"{stem}_market_change.feather",
        }
        allow_lower = {n.lower() for n in allow}

        for info in zf.infolist():
            if info.is_dir():
                continue
            base = os.path.basename(info.filename)
            if not base:
                continue
            if base.lower().endswith(".log"):
                continue
            if base.lower() not in allow_lower:
                continue

            out_path = os.path.join(extract_dir, base)
            with zf.open(info, "r") as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)


def resolve_artifacts(stem: str) -> RunArtifacts:
    """
    Resolve artifacts for a specific run stem, without relying on .last_result.json.

    Handles multiple freqtrade layouts:
    - files written directly in RESULTS_DIR
    - a sibling extracted dir (RESULTS_DIR\\{stem}\\{stem}.json ...)
    - a zip which may need extraction
    """
    json_name = f"{stem}.json"
    zip_name = f"{stem}.zip"
    meta_name = f"{stem}.meta.json"

    root_json = os.path.join(RESULTS_DIR, json_name)
    root_zip = os.path.join(RESULTS_DIR, zip_name)
    root_meta = os.path.join(RESULTS_DIR, meta_name)
    root_config = os.path.join(RESULTS_DIR, f"{stem}_config.json")
    root_signals_json = os.path.join(RESULTS_DIR, f"{stem}_signals.json")
    root_signals_pkl = os.path.join(RESULTS_DIR, f"{stem}_signals.pkl")
    root_rejected_pkl = os.path.join(RESULTS_DIR, f"{stem}_rejected.pkl")
    root_market_change = os.path.join(RESULTS_DIR, f"{stem}_market_change.feather")

    extracted_dir = os.path.join(RESULTS_DIR, stem)
    extracted_json = os.path.join(extracted_dir, json_name)
    extracted_meta = os.path.join(extracted_dir, meta_name)
    extracted_config = os.path.join(extracted_dir, f"{stem}_config.json")
    extracted_signals_json = os.path.join(extracted_dir, f"{stem}_signals.json")
    extracted_signals_pkl = os.path.join(extracted_dir, f"{stem}_signals.pkl")
    extracted_rejected_pkl = os.path.join(extracted_dir, f"{stem}_rejected.pkl")
    extracted_market_change = os.path.join(extracted_dir, f"{stem}_market_change.feather")

    json_path = root_json if os.path.exists(root_json) else None
    if json_path is None and os.path.exists(extracted_json):
        json_path = extracted_json

    signals_path = None
    for candidate in (root_signals_json, root_signals_pkl, extracted_signals_json, extracted_signals_pkl):
        if os.path.exists(candidate):
            signals_path = candidate
            break

    rejected_path = None
    for candidate in (root_rejected_pkl, extracted_rejected_pkl):
        if os.path.exists(candidate):
            rejected_path = candidate
            break

    market_change_path = None
    for candidate in (root_market_change, extracted_market_change):
        if os.path.exists(candidate):
            market_change_path = candidate
            break

    meta_path = root_meta if os.path.exists(root_meta) else None
    config_path = root_config if os.path.exists(root_config) else None
    zip_path = root_zip if os.path.exists(root_zip) else None

    # If anything is missing but we have a zip, try extracting.
    if zip_path is not None and (json_path is None or signals_path is None or meta_path is None or config_path is None or rejected_path is None or market_change_path is None):
        _maybe_extract_zip(zip_path, extracted_dir)
        if os.path.exists(extracted_json):
            json_path = json_path or extracted_json
        if meta_path is None and os.path.exists(extracted_meta):
            meta_path = extracted_meta
        if config_path is None and os.path.exists(extracted_config):
            config_path = extracted_config
        if signals_path is None:
            if os.path.exists(extracted_signals_json):
                signals_path = extracted_signals_json
            elif os.path.exists(extracted_signals_pkl):
                signals_path = extracted_signals_pkl
        if rejected_path is None and os.path.exists(extracted_rejected_pkl):
            rejected_path = extracted_rejected_pkl
        if market_change_path is None and os.path.exists(extracted_market_change):
            market_change_path = extracted_market_change

    return RunArtifacts(
        stem=stem,
        json_path=json_path,
        signals_path=signals_path,
        rejected_path=rejected_path,
        market_change_path=market_change_path,
        config_path=config_path,
        meta_path=meta_path,
        zip_path=zip_path,
        extracted_dir=extracted_dir if os.path.exists(extracted_dir) else None,
    )


def _fmt_num(value: Any, decimals: int = 8) -> str:
    if value is None:
        return ""
    try:
        num = float(value)
    except Exception:
        return str(value)
    text = f"{num:.{decimals}f}".rstrip("0").rstrip(".")
    return text


def _md_escape(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _trade_records_from_trades(trades: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for trade in trades:
        if not isinstance(trade, dict):
            continue

        is_short = bool(trade.get("is_short"))
        amount = trade.get("amount")
        open_date = trade.get("open_date")
        close_date = trade.get("close_date")
        open_rate = trade.get("open_rate")
        close_rate = trade.get("close_rate")

        enter_tag = trade.get("enter_tag")
        exit_reason = trade.get("exit_reason")
        profit_ratio = trade.get("profit_ratio")
        pair = trade.get("pair")
        pair_prefix = f"[{pair}] " if pair else ""

        entry_side = "SELL" if is_short else "BUY"
        exit_side = "BUY" if is_short else "SELL"

        if open_date:
            entry_reason = f"{pair_prefix}enter:{enter_tag}" if enter_tag else f"{pair_prefix}enter"
            rows.append(
                {
                    "time": _md_escape(open_date),
                    "side": entry_side,
                    "amount": _fmt_num(amount),
                    "price": _fmt_num(open_rate),
                    "reason": _md_escape(entry_reason),
                }
            )

        if close_date:
            extra = ""
            if isinstance(profit_ratio, (int, float)):
                extra = f" ({profit_ratio * 100:.2f}%)"
            exit_reason_text = (
                f"{pair_prefix}exit:{exit_reason}{extra}" if exit_reason else f"{pair_prefix}exit{extra}"
            )
            rows.append(
                {
                    "time": _md_escape(close_date),
                    "side": exit_side,
                    "amount": _fmt_num(amount),
                    "price": _fmt_num(close_rate),
                    "reason": _md_escape(exit_reason_text),
                }
            )

    # Best-effort chronological sort without adding extra dependencies.
    rows.sort(key=lambda r: _parse_ts(r.get("time")) or datetime.min)
    return rows


def _read_strategy_code(strategy_name: str) -> tuple[str | None, str | None]:
    candidate = os.path.join(STRATEGY_PATH, f"{strategy_name}.py")
    if os.path.exists(candidate):
        with open(candidate, "r", encoding="utf-8", errors="replace") as f:
            return candidate, f.read()

    try:
        for name in os.listdir(STRATEGY_PATH):
            if name.lower() == f"{strategy_name.lower()}.py":
                path = os.path.join(STRATEGY_PATH, name)
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    return path, f.read()
    except Exception:
        pass

    return None, None


def _trade_distribution(trades: list[dict[str, Any]]) -> dict[str, str]:
    if not trades:
        return {}

    ratios = [t.get("profit_ratio") for t in trades if isinstance(t.get("profit_ratio"), (int, float))]
    if not ratios:
        return {}

    ratios_sorted = sorted(ratios)
    n = len(ratios_sorted)

    def pct(p: float) -> str:
        return f"{p * 100:.2f}%"

    median = ratios_sorted[n // 2] if n % 2 == 1 else (ratios_sorted[n // 2 - 1] + ratios_sorted[n // 2]) / 2
    return {
        "Trade Profit Max %": pct(max(ratios_sorted)),
        "Trade Profit Min %": pct(min(ratios_sorted)),
        "Trade Profit Median %": pct(median),
    }


def _load_signals_frames(signals_path: str, strategy_name: str | None) -> list[Any]:
    if not signals_path or not os.path.exists(signals_path):
        return []

    if signals_path.lower().endswith(".json"):
        # JSON export is inconsistent in shape across versions; keep minimal support.
        data = _safe_read_json(signals_path)
        if data is None:
            return []

        try:
            import pandas as pd  # type: ignore
        except Exception:
            return []

        def as_df(obj: Any) -> Any | None:
            if hasattr(obj, "columns"):
                return obj
            if isinstance(obj, dict):
                # pandas orient="split": {"index": [...], "columns": [...], "data": [...]}
                if (
                    isinstance(obj.get("columns"), list)
                    and isinstance(obj.get("data"), list)
                    and ("index" not in obj or isinstance(obj.get("index"), list))
                ):
                    try:
                        return pd.DataFrame(obj["data"], columns=obj["columns"], index=obj.get("index"))
                    except Exception:
                        return None

                # Simple column-wise dict: {"col": [..], ...}
                if obj and all(isinstance(v, list) for v in obj.values()):
                    try:
                        return pd.DataFrame(obj)
                    except Exception:
                        return None

            # Records: [{"col": ..}, ...]
            if isinstance(obj, list) and (not obj or all(isinstance(x, dict) for x in obj)):
                try:
                    return pd.DataFrame(obj)
                except Exception:
                    return None

            return None

        frames: list[Any] = []
        if isinstance(data, dict):
            for df_like in data.values():
                df = as_df(df_like)
                if df is not None:
                    frames.append(df)
            return frames

        df = as_df(data)
        return [df] if df is not None else []

    if signals_path.lower().endswith(".pkl"):
        # freqtrade exports signals as joblib dump (not plain pickle).
        try:
            import joblib  # type: ignore
        except Exception:
            return []

        obj = joblib.load(signals_path)

        # Possible shapes:
        # - dict[strategy] -> dict[pair] -> DataFrame
        # - dict[pair] -> DataFrame
        # - DataFrame
        if hasattr(obj, "columns"):
            return [obj]

        if isinstance(obj, dict):
            if strategy_name and strategy_name in obj and isinstance(obj[strategy_name], dict):
                obj = obj[strategy_name]

            frames = []
            for v in obj.values():
                if hasattr(v, "columns"):
                    frames.append(v)
                elif isinstance(v, dict):
                    for vv in v.values():
                        if hasattr(vv, "columns"):
                            frames.append(vv)
            return frames

    return []


def analyze_signals(signals_path: str | None, strategy_name: str) -> tuple[dict[str, Any], dict[str, dict[str, float]]]:
    """
    Returns:
    - perf fields (Entry/Exit counts, etc.)
    - gate stats: {dbg_col: {"mean": x, "mean_at_entry": y}}
    """
    if not signals_path or not os.path.exists(signals_path):
        return {}, {}

    frames = _load_signals_frames(signals_path, strategy_name)
    if not frames:
        return {}, {}

    entry_total = 0
    exit_total = 0
    dbg_sums: dict[str, float] = {}
    dbg_counts: dict[str, int] = {}
    dbg_entry_sums: dict[str, float] = {}
    dbg_entry_counts: dict[str, int] = {}

    for df in frames:
        if not hasattr(df, "columns"):
            continue

        columns = set(getattr(df, "columns"))
        entry_col = "enter_short" if "enter_short" in columns else ("enter_long" if "enter_long" in columns else None)
        exit_col = "exit_short" if "exit_short" in columns else ("exit_long" if "exit_long" in columns else None)

        if entry_col:
            try:
                entry_total += int(df[entry_col].fillna(0).astype(int).sum())
            except Exception:
                pass
        if exit_col:
            try:
                exit_total += int(df[exit_col].fillna(0).astype(int).sum())
            except Exception:
                pass

        dbg_cols = [c for c in columns if isinstance(c, str) and c.startswith("dbg_")]
        if not dbg_cols:
            continue

        entry_mask = None
        if entry_col:
            try:
                entry_mask = df[entry_col].fillna(0).astype(int) == 1
            except Exception:
                entry_mask = None

        for c in dbg_cols:
            try:
                series = df[c].astype(float)
            except Exception:
                continue

            valid = series.dropna()
            if not valid.empty:
                dbg_sums[c] = dbg_sums.get(c, 0.0) + float(valid.sum())
                dbg_counts[c] = dbg_counts.get(c, 0) + int(valid.shape[0])

            if entry_mask is not None:
                try:
                    at_entry = series[entry_mask].dropna()
                except Exception:
                    at_entry = None
                if at_entry is not None and not at_entry.empty:
                    dbg_entry_sums[c] = dbg_entry_sums.get(c, 0.0) + float(at_entry.sum())
                    dbg_entry_counts[c] = dbg_entry_counts.get(c, 0) + int(at_entry.shape[0])

    perf: dict[str, Any] = {}
    if entry_total:
        perf["Entry Signals"] = entry_total
    if exit_total:
        perf["Exit Signals"] = exit_total

    gate_stats: dict[str, dict[str, float]] = {}
    for c, s in dbg_sums.items():
        n = dbg_counts.get(c, 0)
        if n <= 0:
            continue
        mean = s / n
        entry_n = dbg_entry_counts.get(c, 0)
        mean_at_entry = (dbg_entry_sums.get(c, 0.0) / entry_n) if entry_n > 0 else float("nan")
        gate_stats[c] = {"mean": mean, "mean_at_entry": mean_at_entry}

    return perf, gate_stats


def parse_result(
    json_path: str | None,
    strategy_name: str,
    signals_path: str | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, float]], list[dict[str, Any]]]:
    if not json_path or not os.path.exists(json_path):
        return {"Status": "Result file not found", "Backtest result": json_path or "N/A"}, {}, []

    with open(json_path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)

    strategy_data = data.get("strategy", {}).get(strategy_name, {})
    trades = strategy_data.get("trades") if isinstance(strategy_data.get("trades"), list) else []

    result: dict[str, Any] = {
        "Total Trades": strategy_data.get("total_trades", 0),
        "Win Rate": f"{strategy_data.get('winrate', 0) * 100:.2f}%",
        "Profit Total %": f"{strategy_data.get('profit_total', 0) * 100:.2f}%",
        "Profit Abs": f"{strategy_data.get('profit_total_abs', 0):.2f}",
        "Profit Factor": f"{strategy_data.get('profit_factor', 0):.2f}",
        "Sharpe": f"{strategy_data.get('sharpe', 0):.2f}" if strategy_data.get("sharpe") else "N/A",
        "Sortino": f"{strategy_data.get('sortino', 0):.2f}" if strategy_data.get("sortino") else "N/A",
        "Calmar": f"{strategy_data.get('calmar', 0):.2f}" if strategy_data.get("calmar") else "N/A",
        "Max Drawdown %": f"{strategy_data.get('max_drawdown_account', 0) * 100:.2f}%" if strategy_data.get("max_drawdown_account") else "N/A",
        "Avg Duration (s)": strategy_data.get("holding_avg_s", "N/A"),
        "Backtest Days": strategy_data.get("backtest_days", "N/A"),
        "CAGR %": f"{strategy_data.get('cagr', 0) * 100:.2f}%" if strategy_data.get("cagr") is not None else "N/A",
    }

    # Trade distribution (fast, small).
    for k, v in _trade_distribution(trades).items():
        result[k] = v

    signals_perf, gate_stats = analyze_signals(signals_path, strategy_name)
    result.update(signals_perf)

    # Simple signal winrate estimate if possible.
    if "Entry Signals" in result and isinstance(result.get("Entry Signals"), int) and result["Entry Signals"] > 0:
        try:
            result["Signal Win Rate"] = f"{(strategy_data.get('total_trades', 0) / result['Entry Signals'] * 100):.2f}%"
        except Exception:
            pass

    return result, gate_stats, trades


def export_freqtrade_trade_point_chart_png(
    backtest_json_path: str,
    signals_pkl_path: str,
    strategy_name: str,
    timerange: str,
    output_path: str,
    pair: str | None = None,
) -> str:
    import json as _json

    try:
        import joblib  # type: ignore
    except Exception as e:
        raise ImportError("joblib is required to read *_signals.pkl") from e

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    with open(backtest_json_path, "r", encoding="utf-8", errors="replace") as f:
        backtest_result = _json.load(f)

    strategy_data = backtest_result.get("strategy", {}).get(strategy_name, {})
    trades = strategy_data.get("trades", []) if isinstance(strategy_data.get("trades"), list) else []
    if pair is None and trades:
        pair = trades[0].get("pair")

    initial_capital = float(strategy_data.get("starting_balance") or 0)
    if initial_capital <= 0:
        initial_capital = 1.0

    obj = joblib.load(signals_pkl_path)
    signals_df = None

    if hasattr(obj, "columns"):
        signals_df = obj
    elif isinstance(obj, dict):
        inner = obj.get(strategy_name) if strategy_name in obj and isinstance(obj[strategy_name], dict) else obj
        if isinstance(inner, dict):
            if pair and pair in inner and hasattr(inner[pair], "columns"):
                signals_df = inner[pair]
            else:
                for v in inner.values():
                    if hasattr(v, "columns"):
                        signals_df = v
                        break

    if signals_df is None or signals_df.empty:
        raise ValueError("Unable to resolve signals dataframe from signals_pkl_path")

    df = signals_df.copy()
    if "date" not in df.columns:
        raise ValueError("signals dataframe missing 'date' column")

    times = pd.to_datetime(df["date"], utc=True, errors="coerce").dt.tz_convert(None)
    close = pd.to_numeric(df.get("close"), errors="coerce")
    if close is None:
        raise ValueError("signals dataframe missing 'close' column")

    ma7 = pd.to_numeric(df.get("ma7"), errors="coerce") if "ma7" in df.columns else close.rolling(window=7).mean()
    ma25 = pd.to_numeric(df.get("ma25"), errors="coerce") if "ma25" in df.columns else close.rolling(window=25).mean()

    buy_x: list[pd.Timestamp] = []
    buy_y: list[float] = []
    sell_x: list[pd.Timestamp] = []
    sell_y: list[float] = []
    profit_x: list[pd.Timestamp] = []
    profit_y: list[float] = []

    cum_profit = 0.0

    def _to_naive(ts) -> pd.Timestamp | None:
        if not ts:
            return None
        try:
            t = pd.Timestamp(ts)
        except Exception:
            return None
        if getattr(t, "tzinfo", None) is not None:
            try:
                t = t.tz_convert(None)
            except Exception:
                t = t.tz_localize(None)
        return t

    for trade in sorted(trades, key=lambda x: x.get("close_timestamp") or x.get("close_date") or ""):
        if pair and trade.get("pair") != pair:
            continue

        is_short = bool(trade.get("is_short"))
        open_ts = _to_naive(trade.get("open_date"))
        close_ts = _to_naive(trade.get("close_date"))
        if open_ts is None or close_ts is None:
            continue

        open_rate = float(trade.get("open_rate") or 0.0)
        close_rate = float(trade.get("close_rate") or 0.0)
        profit_abs = float(trade.get("profit_abs") or 0.0)

        if is_short:
            sell_x.append(open_ts)
            sell_y.append(open_rate)
            buy_x.append(close_ts)
            buy_y.append(close_rate)
        else:
            buy_x.append(open_ts)
            buy_y.append(open_rate)
            sell_x.append(close_ts)
            sell_y.append(close_rate)

        cum_profit += profit_abs
        profit_x.append(close_ts)
        profit_y.append(cum_profit / initial_capital)

    fig, ax1 = plt.subplots(figsize=(18, 8))
    ax1.plot(times, close, color="#000000", linewidth=0.8, label="close")
    ax1.plot(times, ma7, color="#F19C38", linewidth=0.8, label="ma7")
    ax1.plot(times, ma25, color="#EA3DF7", linewidth=0.8, label="ma25")

    if buy_x:
        ax1.scatter(buy_x, buy_y, color="#2EBD85", s=10, marker="^", label="BUY", alpha=0.8)
    if sell_x:
        ax1.scatter(sell_x, sell_y, color="#F6465D", s=10, marker="v", label="SELL", alpha=0.8)

    ax1.set_title(f"{strategy_name} {pair or ''} {timerange}")
    ax1.set_ylabel("price")
    ax1.grid(True, alpha=0.2)

    ax2 = ax1.twinx()
    if profit_x:
        ax2.plot(profit_x, profit_y, color="#138535", linewidth=1.0, label="accu_profit (ratio)")
    ax2.set_ylabel("accu_profit (ratio)")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def build_backtest_markdown(
    strategy_name: str,
    timerange: str,
    artifacts: RunArtifacts,
    perf: dict[str, Any],
    gate_stats: dict[str, dict[str, float]],
    diagnostics: dict[str, Any] | None = None,
    trades: list[dict[str, Any]] | None = None,
    chart_paths: list[str] | None = None,
) -> str:
    strategy_file, strategy_code = _read_strategy_code(strategy_name)

    lines: list[str] = []
    lines.append("# Freqtrade Backtesting Result")
    lines.append("")
    lines.append("## Run")
    lines.append(f"- Strategy: `{strategy_name}`")
    lines.append(f"- Timerange: `{timerange}`")
    lines.append(f"- Stem: `{artifacts.stem}`")
    if artifacts.json_path:
        lines.append(f"- Backtest result: `{artifacts.json_path}`")
    if artifacts.signals_path:
        lines.append(f"- Signals: `{artifacts.signals_path}`")
    if artifacts.rejected_path:
        lines.append(f"- Rejected: `{artifacts.rejected_path}`")
    if artifacts.market_change_path:
        lines.append(f"- Market Change: `{artifacts.market_change_path}`")
    if artifacts.meta_path:
        lines.append(f"- Meta: `{artifacts.meta_path}`")
    if artifacts.zip_path:
        lines.append(f"- Zip: `{artifacts.zip_path}`")
    if strategy_file:
        lines.append(f"- Strategy file: `{strategy_file}`")
    if chart_paths:
        for p in chart_paths:
            lines.append(f"- Trade chart: `{p}`")
    lines.append("")

    lines.append("## Summary")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    for k, v in perf.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    if trades:
        trade_rows = _trade_records_from_trades(trades)
        if trade_rows:
            lines.append("## Trades (交易紀錄)")
            lines.append("| 時間 | 買賣 | 數量 | 價格 | 交易原因 |")
            lines.append("|---|---|---:|---:|---|")
            for r in trade_rows:
                lines.append(
                    f"| {r.get('time','')} | {r.get('side','')} | {r.get('amount','')} | {r.get('price','')} | {r.get('reason','')} |"
                )
            lines.append("")

    if gate_stats:
        lines.append("## Signals Gate Stats")
        lines.append("| Column | Mean | Mean@Entry |")
        lines.append("|---|---:|---:|")
        for c in sorted(gate_stats.keys()):
            mean = gate_stats[c].get("mean")
            mean_at_entry = gate_stats[c].get("mean_at_entry")
            mean_s = f"{mean:.4f}" if isinstance(mean, (int, float)) else "N/A"
            mean_entry_s = f"{mean_at_entry:.4f}" if isinstance(mean_at_entry, (int, float)) and mean_at_entry == mean_at_entry else "N/A"
            lines.append(f"| `{c}` | {mean_s} | {mean_entry_s} |")
        lines.append("")

    if diagnostics:
        lines.append("## Deep Diagnostics")

        mae_mfe = diagnostics.get("mae_mfe", {}) if isinstance(diagnostics.get("mae_mfe"), dict) else {}
        lines.append("### MAE/MFE Efficiency")
        lines.append("| Metric | Value |")
        lines.append("|---|---:|")
        lines.append(f"| Avg MAE % | {mae_mfe.get('avg_mae_pct', 0.0)} |")
        lines.append(f"| Avg MFE % | {mae_mfe.get('avg_mfe_pct', 0.0)} |")
        lines.append(f"| Profit Giveback % (winners) | {mae_mfe.get('profit_giveback_pct', 0.0)} |")
        lines.append("")
        mae_hist = mae_mfe.get("mae_hist", [])
        mfe_hist = mae_mfe.get("mfe_hist", [])
        if mae_hist:
            lines.append("MAE Distribution:")
            lines.append("```text")
            for item in mae_hist:
                lines.append(str(item))
            lines.append("```")
        if mfe_hist:
            lines.append("MFE Distribution:")
            lines.append("```text")
            for item in mfe_hist:
                lines.append(str(item))
            lines.append("```")
        lines.append("")

        rej = diagnostics.get("rejected_vs_executed", {}) if isinstance(diagnostics.get("rejected_vs_executed"), dict) else {}
        lines.append("### Rejected vs Executed")
        lines.append("| Metric | Value |")
        lines.append("|---|---:|")
        lines.append(f"| Rejected Total | {rej.get('rejected_total', 0)} |")
        lines.append(f"| Rejected Win Rate % | {rej.get('rejected_winrate_pct', 0.0)} |")
        lines.append(f"| Rejected Avg Hypothetical % | {rej.get('rejected_avg_hypothetical_pct', 0.0)} |")
        lines.append(f"| Executed Win Rate % | {rej.get('executed_winrate_pct', 0.0)} |")
        lines.append(f"| Executed Avg Profit % | {rej.get('executed_avg_profit_pct', 0.0)} |")
        lines.append(f"| Opportunity Cost (Abs) | {rej.get('opportunity_cost_abs', 0.0)} |")
        lines.append("")

        market = diagnostics.get("market_condition", {}) if isinstance(diagnostics.get("market_condition"), dict) else {}
        market_summary = market.get("summary", {}) if isinstance(market.get("summary"), dict) else {}
        market_rows = market.get("rows", []) if isinstance(market.get("rows"), list) else []
        lines.append("### Market Regime")
        lines.append(f"- Status: `{market_summary.get('status', 'N/A')}`")
        lines.append(f"- Rally Win Rate %: `{market_summary.get('rally_winrate_pct', 0.0)}`")
        lines.append(f"- Range Win Rate %: `{market_summary.get('range_winrate_pct', 0.0)}`")
        lines.append(f"- Downtrend Win Rate %: `{market_summary.get('downtrend_winrate_pct', 0.0)}`")
        if market_rows:
            lines.append("")
            lines.append("| Regime | Trades | Win Rate % | Avg Profit % |")
            lines.append("|---|---:|---:|---:|")
            for row in market_rows:
                lines.append(
                    f"| {row.get('market_regime','')} | {row.get('trades',0)} | {row.get('winrate_pct',0.0)} | {row.get('avg_profit_pct',0.0)} |"
                )
        lines.append("")

        gates = diagnostics.get("gate_filter_funnel", [])
        if isinstance(gates, list) and gates:
            lines.append("### Gate Filter Funnel")
            lines.append("| Filter | Trigger % | Blocking % | Wrong-Filtered % | Precision % |")
            lines.append("|---|---:|---:|---:|---:|")
            for row in gates:
                lines.append(
                    f"| `{row.get('filter','')}` | {row.get('trigger_rate_pct',0.0)} | {row.get('blocking_rate_pct',0.0)} | {row.get('wrong_filtered_rate_pct',0.0)} | {row.get('filtering_precision_pct',0.0)} |"
                )
            lines.append("")

        insights = diagnostics.get("insights", [])
        if isinstance(insights, list) and insights:
            lines.append("### Diagnostic Conclusions")
            for s in insights:
                lines.append(f"- {s}")
            lines.append("")

    if strategy_code:
        lines.append("## Strategy Code")
        lines.append("```python")
        lines.append(strategy_code.rstrip())
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def _write_report(stem: str, strategy_name: str, markdown: str) -> str:
    _ensure_dir(REPORTS_DIR)
    name = f"report_{stem}_{strategy_name}.md"
    out = os.path.join(REPORTS_DIR, name)
    with open(out, "w", encoding="utf-8", errors="replace") as f:
        f.write(markdown)
    return out


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _pct(value: float, decimals: int = 4) -> float:
    return round(value * 100.0, decimals)


def _safe_div(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return a / b


def _as_iso(ts: Any) -> str:
    parsed = _parse_ts(ts)
    if parsed is None:
        return ""
    return parsed.isoformat()


def _as_timestamp(ts: Any) -> float | None:
    parsed = _parse_ts(ts)
    if parsed is None:
        return None
    try:
        return parsed.timestamp()
    except Exception:
        return None


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if p <= 0:
        return float(min(values))
    if p >= 100:
        return float(max(values))
    s = sorted(values)
    rank = (len(s) - 1) * (p / 100.0)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return float(s[lo])
    frac = rank - lo
    return float(s[lo] * (1.0 - frac) + s[hi] * frac)


def _write_csv(path: str, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _hash_file(path: str | None) -> str:
    if not path or not os.path.exists(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _git_commit_hash() -> str:
    try:
        cp = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return (cp.stdout or "").strip() if cp.returncode == 0 else ""
    except Exception:
        return ""


def _normalize_trades(trades: list[dict[str, Any]], timeframe: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, trade in enumerate(trades, start=1):
        if not isinstance(trade, dict):
            continue

        open_ts = trade.get("open_date")
        close_ts = trade.get("close_date")
        open_dt = _parse_ts(open_ts)
        close_dt = _parse_ts(close_ts)

        duration_min = 0.0
        if open_dt and close_dt:
            try:
                duration_min = (close_dt - open_dt).total_seconds() / 60.0
            except Exception:
                duration_min = 0.0

        fee_open = _to_float(
            trade.get("fee_open_cost", trade.get("fee_open", 0.0)),
            0.0,
        )
        fee_close = _to_float(
            trade.get("fee_close_cost", trade.get("fee_close", 0.0)),
            0.0,
        )
        fee_total = fee_open + fee_close

        profit_ratio = _to_float(trade.get("profit_ratio"), 0.0)
        open_rate = _to_float(trade.get("open_rate"), 0.0)
        min_rate = _to_float(trade.get("min_rate"), 0.0)
        max_rate = _to_float(trade.get("max_rate"), 0.0)
        is_short = bool(trade.get("is_short"))

        mae_ratio = 0.0
        mfe_ratio = 0.0
        if open_rate > 0:
            if is_short:
                if max_rate > 0:
                    mae_ratio = (max_rate - open_rate) / open_rate
                if min_rate > 0:
                    mfe_ratio = (open_rate - min_rate) / open_rate
            else:
                if min_rate > 0:
                    mae_ratio = (min_rate - open_rate) / open_rate
                if max_rate > 0:
                    mfe_ratio = (max_rate - open_rate) / open_rate

        efficiency = _safe_div(mfe_ratio, (mfe_ratio + abs(mae_ratio))) if (mfe_ratio + abs(mae_ratio)) > 0 else 0.0

        row = {
            "trade_id": trade.get("trade_id", trade.get("id", idx)),
            "pair": trade.get("pair", ""),
            "direction": "short" if is_short else "long",
            "timeframe": timeframe,
            "open_time": _as_timestamp(open_ts) or "",
            "close_time": _as_timestamp(close_ts) or "",
            "open_date_utc": _as_iso(open_ts),
            "close_date_utc": _as_iso(close_ts),
            "duration_min": round(duration_min, 4),
            "open_rate": open_rate,
            "close_rate": _to_float(trade.get("close_rate"), 0.0),
            "min_rate": min_rate,
            "max_rate": max_rate,
            "stake_amount": _to_float(trade.get("stake_amount"), _to_float(trade.get("stake_amount_fiat"), 0.0)),
            "amount": _to_float(trade.get("amount"), 0.0),
            "profit_abs": _to_float(trade.get("profit_abs"), 0.0),
            "profit_ratio": profit_ratio,
            "profit_pct": _pct(profit_ratio, 4),
            "max_profit_ratio": _to_float(trade.get("max_profit_ratio"), mfe_ratio),
            "max_drawdown_ratio": _to_float(trade.get("max_drawdown", trade.get("min_profit_ratio", mae_ratio)), mae_ratio),
            "mfe_ratio": mfe_ratio,
            "mae_ratio": mae_ratio,
            "entry_efficiency_score": round(efficiency, 8),
            "fee_open": fee_open,
            "fee_close": fee_close,
            "fee_total": fee_total,
            "slippage_est": 0.0,
            "enter_tag": trade.get("enter_tag", ""),
            "exit_reason": trade.get("exit_reason", ""),
            "exit_tag": trade.get("exit_tag", ""),
            "stop_loss_hit": 1 if "stop" in str(trade.get("exit_reason", "")).lower() else 0,
            "roi_hit": 1 if "roi" in str(trade.get("exit_reason", "")).lower() else 0,
            "trailing_stop_hit": 1 if "trail" in str(trade.get("exit_reason", "")).lower() else 0,
            "protection_blocked": 0,
        }
        rows.append(row)

    rows.sort(key=lambda r: (r.get("close_time") or float("inf"), r.get("trade_id")))
    return rows


def _build_equity_and_daily(trade_rows: list[dict[str, Any]], starting_balance: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    equity = starting_balance if starting_balance > 0 else 1.0
    peak = equity
    equity_rows: list[dict[str, Any]] = []
    daily_map: dict[str, dict[str, Any]] = {}

    for idx, row in enumerate(trade_rows, start=1):
        pnl = _to_float(row.get("profit_abs"), 0.0)
        prev_equity = equity
        equity += pnl
        if equity > peak:
            peak = equity
        dd = _safe_div(peak - equity, peak)
        close_iso = str(row.get("close_date_utc") or "")
        day = close_iso[:10] if close_iso else ""

        equity_rows.append(
            {
                "index": idx,
                "timestamp": close_iso,
                "trade_id": row.get("trade_id"),
                "pair": row.get("pair"),
                "pnl_abs": round(pnl, 8),
                "pnl_pct": round(_safe_div(pnl, prev_equity), 8),
                "equity": round(equity, 8),
                "drawdown_pct": round(_pct(dd, 6), 6),
            }
        )

        if day:
            if day not in daily_map:
                daily_map[day] = {"date": day, "pnl_abs": 0.0, "last_equity": prev_equity, "max_peak": peak}
            daily_map[day]["pnl_abs"] += pnl
            daily_map[day]["last_equity"] = equity
            daily_map[day]["max_peak"] = max(daily_map[day]["max_peak"], peak)

    daily_rows: list[dict[str, Any]] = []
    for day in sorted(daily_map.keys()):
        item = daily_map[day]
        last_equity = _to_float(item.get("last_equity"), 0.0)
        pnl_abs = _to_float(item.get("pnl_abs"), 0.0)
        prev = last_equity - pnl_abs
        daily_rows.append(
            {
                "date": day,
                "pnl_abs": round(pnl_abs, 8),
                "pnl_pct": round(_safe_div(pnl_abs, prev), 8),
                "equity": round(last_equity, 8),
                "drawdown_pct": round(_pct(_safe_div(_to_float(item.get("max_peak"), 0.0) - last_equity, _to_float(item.get("max_peak"), 0.0)), 6), 6),
            }
        )

    return equity_rows, daily_rows


def _build_pair_breakdown(trade_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in trade_rows:
        pair = str(row.get("pair") or "N/A")
        groups.setdefault(pair, []).append(row)

    out: list[dict[str, Any]] = []
    for pair in sorted(groups.keys()):
        rows = groups[pair]
        profits = [_to_float(r.get("profit_abs"), 0.0) for r in rows]
        ratios = [_to_float(r.get("profit_ratio"), 0.0) for r in rows]
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p < 0]
        gross_profit = sum(wins)
        gross_loss_abs = abs(sum(losses))
        out.append(
            {
                "pair": pair,
                "trades": len(rows),
                "winrate_pct": round(_pct(_safe_div(len(wins), len(rows))), 4),
                "profit_factor": round(_safe_div(gross_profit, gross_loss_abs), 6) if gross_loss_abs > 0 else 0.0,
                "net_pnl": round(sum(profits), 8),
                "max_drawdown_proxy_pct": round(_pct(abs(min(ratios)) if ratios else 0.0), 4),
                "avg_duration_min": round(statistics.mean([_to_float(r.get("duration_min"), 0.0) for r in rows]), 4) if rows else 0.0,
                "avg_profit_pct": round(_pct(statistics.mean(ratios) if ratios else 0.0), 4),
                "median_profit_pct": round(_pct(statistics.median(ratios) if ratios else 0.0), 4),
            }
        )
    return out


def _build_entry_exit_reason(trade_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in trade_rows:
        key = (str(row.get("enter_tag") or ""), str(row.get("exit_reason") or ""))
        groups.setdefault(key, []).append(row)

    out: list[dict[str, Any]] = []
    for (enter_tag, exit_reason), rows in sorted(groups.items(), key=lambda x: (x[0][1], x[0][0])):
        profits = [_to_float(r.get("profit_abs"), 0.0) for r in rows]
        mfe = [_to_float(r.get("max_profit_ratio"), 0.0) for r in rows]
        mae = [_to_float(r.get("max_drawdown_ratio"), 0.0) for r in rows]
        out.append(
            {
                "enter_tag": enter_tag,
                "exit_reason": exit_reason,
                "count": len(rows),
                "net_pnl": round(sum(profits), 8),
                "avg_pnl": round(statistics.mean(profits) if profits else 0.0, 8),
                "avg_mfe_pct": round(_pct(statistics.mean(mfe) if mfe else 0.0), 4),
                "avg_mae_pct": round(_pct(statistics.mean(mae) if mae else 0.0), 4),
            }
        )
    return out


def _build_time_breakdown(trade_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in trade_rows:
        open_iso = str(row.get("open_date_utc") or "")
        dt = _parse_ts(open_iso)
        if dt is None:
            continue
        key = (dt.weekday(), dt.hour)
        groups.setdefault(key, []).append(row)

    out: list[dict[str, Any]] = []
    for (weekday, hour), rows in sorted(groups.items()):
        profits = [_to_float(r.get("profit_abs"), 0.0) for r in rows]
        ratios = [_to_float(r.get("profit_ratio"), 0.0) for r in rows]
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p < 0]
        out.append(
            {
                "weekday": weekday,
                "hour": hour,
                "trades": len(rows),
                "winrate_pct": round(_pct(_safe_div(len(wins), len(rows))), 4),
                "expectancy_pct": round(_pct(statistics.mean(ratios) if ratios else 0.0), 4),
                "pnl_abs": round(sum(profits), 8),
                "profit_factor": round(_safe_div(sum(wins), abs(sum(losses))), 6) if losses else 0.0,
            }
        )
    return out


def _build_summary(
    trade_rows: list[dict[str, Any]],
    equity_rows: list[dict[str, Any]],
    daily_rows: list[dict[str, Any]],
    strategy_data: dict[str, Any],
) -> dict[str, Any]:
    profits = [_to_float(r.get("profit_abs"), 0.0) for r in trade_rows]
    ratios = [_to_float(r.get("profit_ratio"), 0.0) for r in trade_rows]
    wins = [p for p in profits if p > 0]
    losses = [p for p in profits if p < 0]

    gross_profit = sum(wins)
    gross_loss = sum(losses)
    gross_loss_abs = abs(gross_loss)
    net_profit = sum(profits)

    max_consec_wins = 0
    max_consec_losses = 0
    cw = 0
    cl = 0
    for p in profits:
        if p > 0:
            cw += 1
            cl = 0
        elif p < 0:
            cl += 1
            cw = 0
        else:
            cw = 0
            cl = 0
        max_consec_wins = max(max_consec_wins, cw)
        max_consec_losses = max(max_consec_losses, cl)

    dd_values = [_to_float(r.get("drawdown_pct"), 0.0) / 100.0 for r in equity_rows]
    max_dd = max(dd_values) if dd_values else 0.0
    ulcer_index = math.sqrt(statistics.mean([d * d for d in dd_values])) if dd_values else 0.0

    in_dd_points = 0
    longest_dd_streak = 0
    current_dd_streak = 0
    for d in dd_values:
        if d > 0:
            in_dd_points += 1
            current_dd_streak += 1
        else:
            longest_dd_streak = max(longest_dd_streak, current_dd_streak)
            current_dd_streak = 0
    longest_dd_streak = max(longest_dd_streak, current_dd_streak)

    negative_ratios = [r for r in ratios if r < 0]
    downside_dev = math.sqrt(statistics.mean([r * r for r in negative_ratios])) if negative_ratios else 0.0

    fees_total = sum(_to_float(r.get("fee_total"), 0.0) for r in trade_rows)
    backtest_days = _to_float(strategy_data.get("backtest_days"), 0.0)

    summary = {
        "total_trades": len(trade_rows),
        "winrate_pct": round(_pct(_safe_div(len(wins), len(trade_rows))), 4),
        "avg_profit_pct": round(_pct(statistics.mean(ratios) if ratios else 0.0), 4),
        "median_profit_pct": round(_pct(statistics.median(ratios) if ratios else 0.0), 4),
        "profit_factor": round(_safe_div(gross_profit, gross_loss_abs), 8) if gross_loss_abs > 0 else 0.0,
        "expectancy_pct": round(_pct(statistics.mean(ratios) if ratios else 0.0), 4),
        "gross_profit": round(gross_profit, 8),
        "gross_loss": round(gross_loss, 8),
        "net_profit": round(net_profit, 8),
        "max_consecutive_wins": max_consec_wins,
        "max_consecutive_losses": max_consec_losses,
        "max_drawdown_pct": round(_pct(max_dd), 6),
        "ulcer_index": round(ulcer_index, 8),
        "time_in_drawdown_points": in_dd_points,
        "longest_drawdown_streak_points": longest_dd_streak,
        "downside_deviation": round(downside_dev, 8),
        "p5_profit_pct": round(_pct(_percentile(ratios, 5)), 4),
        "p25_profit_pct": round(_pct(_percentile(ratios, 25)), 4),
        "p50_profit_pct": round(_pct(_percentile(ratios, 50)), 4),
        "p75_profit_pct": round(_pct(_percentile(ratios, 75)), 4),
        "p95_profit_pct": round(_pct(_percentile(ratios, 95)), 4),
        "tail_worst_1pct_avg_pct": round(_pct(statistics.mean(sorted(ratios)[:max(1, len(ratios) // 100)]) if ratios else 0.0), 4),
        "tail_best_1pct_avg_pct": round(_pct(statistics.mean(sorted(ratios)[-max(1, len(ratios) // 100):]) if ratios else 0.0), 4),
        "fees_total": round(fees_total, 8),
        "fees_pct_of_gross_profit": round(_pct(_safe_div(fees_total, gross_profit)), 4) if gross_profit > 0 else 0.0,
        "avg_trade_duration_min": round(statistics.mean([_to_float(r.get("duration_min"), 0.0) for r in trade_rows]) if trade_rows else 0.0, 4),
        "trades_per_day": round(_safe_div(len(trade_rows), backtest_days), 6) if backtest_days > 0 else 0.0,
        "daily_rows": len(daily_rows),
    }

    if len(ratios) >= 3:
        try:
            summary["skewness"] = round(statistics.mean([(x - statistics.mean(ratios)) ** 3 for x in ratios]) / ((statistics.pstdev(ratios) or 1.0) ** 3), 8)
        except Exception:
            summary["skewness"] = 0.0
    if len(ratios) >= 4:
        try:
            mu = statistics.mean(ratios)
            var = statistics.pvariance(ratios)
            summary["kurtosis"] = round(statistics.mean([(x - mu) ** 4 for x in ratios]) / ((var or 1.0) ** 2), 8)
        except Exception:
            summary["kurtosis"] = 0.0

    return summary


def _scenario_metrics(trade_rows: list[dict[str, Any]], profit_key: str, start_balance: float) -> dict[str, Any]:
    profits = [_to_float(r.get(profit_key), 0.0) for r in trade_rows]
    wins = [p for p in profits if p > 0]
    losses = [p for p in profits if p < 0]

    equity = start_balance if start_balance > 0 else 1.0
    peak = equity
    max_dd = 0.0
    for p in profits:
        equity += p
        peak = max(peak, equity)
        max_dd = max(max_dd, _safe_div(peak - equity, peak))

    return {
        "net_profit": round(sum(profits), 8),
        "profit_factor": round(_safe_div(sum(wins), abs(sum(losses))), 8) if losses else 0.0,
        "winrate_pct": round(_pct(_safe_div(len(wins), len(trade_rows))), 4) if trade_rows else 0.0,
        "max_drawdown_pct": round(_pct(max_dd), 6),
    }


def _build_cost_impact(trade_rows: list[dict[str, Any]], start_balance: float) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in trade_rows:
        rr = dict(row)
        stake = _to_float(row.get("stake_amount"), 0.0)
        fee = _to_float(row.get("fee_total"), 0.0)
        base = _to_float(row.get("profit_abs"), 0.0)
        rr["_baseline"] = base
        rr["_fee_removed"] = base + fee
        rr["_fee_and_slip_removed"] = base + fee
        for slip in (0.0002, 0.0005, 0.001):
            rr[f"_slip_{slip}"] = base - stake * (2.0 * slip)
        enriched.append(rr)

    scenarios = [
        ("baseline", "_baseline"),
        ("slippage_0.02pct_per_side", "_slip_0.0002"),
        ("slippage_0.05pct_per_side", "_slip_0.0005"),
        ("slippage_0.10pct_per_side", "_slip_0.001"),
        ("fee_removed", "_fee_removed"),
        ("fee_and_slippage_removed", "_fee_and_slip_removed"),
    ]

    out: list[dict[str, Any]] = []
    for name, key in scenarios:
        m = _scenario_metrics(enriched, key, start_balance)
        out.append({"scenario": name, **m})
    return out


def _load_signal_pair_frames(signals_path: str | None, strategy_name: str) -> dict[str, Any]:
    if not signals_path or not os.path.exists(signals_path):
        return {}

    if not signals_path.lower().endswith(".pkl"):
        return {}

    try:
        import joblib  # type: ignore
    except Exception:
        return {}

    obj = joblib.load(signals_path)
    if hasattr(obj, "columns"):
        return {"*": obj}

    if not isinstance(obj, dict):
        return {}

    inner = obj.get(strategy_name) if strategy_name in obj and isinstance(obj[strategy_name], dict) else obj
    if not isinstance(inner, dict):
        return {}

    out: dict[str, Any] = {}
    for pair, frame in inner.items():
        if hasattr(frame, "columns"):
            out[str(pair)] = frame
    return out


def _build_signal_index(signals_path: str | None, strategy_name: str) -> dict[str, dict[str, Any]]:
    pair_frames = _load_signal_pair_frames(signals_path, strategy_name)
    if not pair_frames:
        return {}

    try:
        import pandas as pd  # type: ignore
    except Exception:
        return {}

    index_map: dict[str, dict[str, Any]] = {}
    for pair, frame in pair_frames.items():
        if "date" not in frame.columns:
            continue

        df = frame.copy()
        ts = pd.to_datetime(df["date"], utc=True, errors="coerce")
        df = df.assign(__ts=ts)
        df = df.dropna(subset=["__ts"]).sort_values("__ts")
        if df.empty:
            continue

        ts_values = [int(x.value) for x in df["__ts"].tolist()]
        row_values = [r for _, r in df.iterrows()]
        index_map[pair] = {"ts": ts_values, "rows": row_values}

    return index_map


def _find_signal_row(index_map: dict[str, dict[str, Any]], pair: str, ts_iso: Any) -> tuple[Any | None, int]:
    idx = index_map.get(pair) or index_map.get("*")
    if not idx:
        return None, -1

    ts = _parse_ts(ts_iso)
    if ts is None:
        return None, -1

    key_ns = int(ts.timestamp() * 1_000_000_000)
    ts_list: list[int] = idx["ts"]
    rows_list: list[Any] = idx["rows"]
    pos = bisect_right(ts_list, key_ns) - 1
    if pos < 0 or pos >= len(rows_list):
        return None, -1
    return rows_list[pos], pos


def _enrich_trades_with_market_context(
    trade_rows: list[dict[str, Any]],
    index_map: dict[str, dict[str, Any]],
) -> None:
    for row in trade_rows:
        pair = str(row.get("pair") or "")
        open_ts = row.get("open_date_utc")
        close_ts = row.get("close_date_utc")

        entry_sr, _ = _find_signal_row(index_map, pair, open_ts)
        exit_sr, _ = _find_signal_row(index_map, pair, close_ts)

        entry_spread = 0.0
        exit_spread = 0.0
        entry_ref = _to_float(row.get("open_rate"), 0.0)
        exit_ref = _to_float(row.get("close_rate"), 0.0)

        if entry_sr is not None:
            entry_close = _to_float(entry_sr.get("close"), 0.0)
            entry_high = _to_float(entry_sr.get("high"), entry_close)
            entry_low = _to_float(entry_sr.get("low"), entry_close)
            if entry_close > 0:
                entry_spread = _safe_div(entry_high - entry_low, entry_close)
                entry_ref = entry_close

        if exit_sr is not None:
            exit_close = _to_float(exit_sr.get("close"), 0.0)
            exit_high = _to_float(exit_sr.get("high"), exit_close)
            exit_low = _to_float(exit_sr.get("low"), exit_close)
            if exit_close > 0:
                exit_spread = _safe_div(exit_high - exit_low, exit_close)
                exit_ref = exit_close

        is_short = str(row.get("direction")) == "short"
        open_rate = _to_float(row.get("open_rate"), 0.0)
        close_rate = _to_float(row.get("close_rate"), 0.0)

        if is_short:
            slippage_entry = max(0.0, _safe_div(entry_ref - open_rate, entry_ref)) if entry_ref > 0 else 0.0
            slippage_exit = max(0.0, _safe_div(close_rate - exit_ref, exit_ref)) if exit_ref > 0 else 0.0
        else:
            slippage_entry = max(0.0, _safe_div(open_rate - entry_ref, entry_ref)) if entry_ref > 0 else 0.0
            slippage_exit = max(0.0, _safe_div(exit_ref - close_rate, exit_ref)) if exit_ref > 0 else 0.0

        row["entry_spread"] = round(entry_spread, 8)
        row["exit_spread"] = round(exit_spread, 8)
        row["expected_fill_price_entry"] = round(entry_ref, 8)
        row["expected_fill_price_exit"] = round(exit_ref, 8)
        row["assumed_fill_price_entry"] = round(open_rate, 8)
        row["assumed_fill_price_exit"] = round(close_rate, 8)
        row["slippage_entry"] = round(slippage_entry, 8)
        row["slippage_exit"] = round(slippage_exit, 8)
        row["slippage_est"] = round(slippage_entry + slippage_exit, 8)

        idx = index_map.get(pair) or index_map.get("*")
        if not idx:
            row["mfe_ratio"] = _to_float(row.get("max_profit_ratio"), 0.0)
            row["mae_ratio"] = _to_float(row.get("max_drawdown_ratio"), 0.0)
            row["mfe_price"] = 0.0
            row["mae_price"] = 0.0
            row["mfe_ts"] = ""
            row["mae_ts"] = ""
            continue

        ts_list: list[int] = idx["ts"]
        rows_list: list[Any] = idx["rows"]
        open_dt = _parse_ts(open_ts)
        close_dt = _parse_ts(close_ts)
        if open_dt is None or close_dt is None:
            continue

        start_ns = int(open_dt.timestamp() * 1_000_000_000)
        end_ns = int(close_dt.timestamp() * 1_000_000_000)
        start_pos = max(0, bisect_right(ts_list, start_ns) - 1)
        end_pos = max(start_pos + 1, bisect_right(ts_list, end_ns))
        if end_pos <= start_pos:
            end_pos = min(len(rows_list), start_pos + 1)

        window = rows_list[start_pos:end_pos]
        if not window:
            continue

        highs: list[tuple[float, Any]] = []
        lows: list[tuple[float, Any]] = []
        for sr in window:
            highs.append((_to_float(sr.get("high"), _to_float(sr.get("close"), 0.0)), sr.get("date")))
            lows.append((_to_float(sr.get("low"), _to_float(sr.get("close"), 0.0)), sr.get("date")))

        if open_rate <= 0:
            continue

        if is_short:
            mfe_price, mfe_ts = min(lows, key=lambda x: x[0])
            mae_price, mae_ts = max(highs, key=lambda x: x[0])
            mfe_ratio = _safe_div(open_rate - mfe_price, open_rate)
            mae_ratio = _safe_div(open_rate - mae_price, open_rate)
        else:
            mfe_price, mfe_ts = max(highs, key=lambda x: x[0])
            mae_price, mae_ts = min(lows, key=lambda x: x[0])
            mfe_ratio = _safe_div(mfe_price - open_rate, open_rate)
            mae_ratio = _safe_div(mae_price - open_rate, open_rate)

        row["mfe_ratio"] = round(mfe_ratio, 8)
        row["mae_ratio"] = round(mae_ratio, 8)
        row["mfe_price"] = round(mfe_price, 8)
        row["mae_price"] = round(mae_price, 8)
        row["mfe_ts"] = _as_iso(mfe_ts)
        row["mae_ts"] = _as_iso(mae_ts)
        row["max_profit_ratio"] = round(mfe_ratio, 8)
        row["max_drawdown_ratio"] = round(mae_ratio, 8)


def _timeframe_to_minutes(timeframe: str) -> int:
    tf = (timeframe or "").strip().lower()
    if not tf:
        return 15
    units = {"m": 1, "h": 60, "d": 1440}
    try:
        if tf[-1] in units:
            return int(tf[:-1]) * units[tf[-1]]
        return int(tf)
    except Exception:
        return 15


def _load_rejected_rows(rejected_path: str | None, strategy_name: str) -> list[dict[str, Any]]:
    if not rejected_path or not os.path.exists(rejected_path):
        return []
    try:
        import joblib  # type: ignore
    except Exception:
        return []

    try:
        obj = joblib.load(rejected_path)
    except Exception:
        try:
            import pandas as pd  # type: ignore
            obj = pd.read_pickle(rejected_path)
        except Exception:
            return []

    rows: list[dict[str, Any]] = []

    def append_df(df: Any, pair_hint: str = "") -> None:
        if not hasattr(df, "iterrows"):
            return
        for _, sr in df.iterrows():
            item = sr.to_dict() if hasattr(sr, "to_dict") else dict(sr)
            if pair_hint and not item.get("pair"):
                item["pair"] = pair_hint
            rows.append(item)

    if hasattr(obj, "iterrows"):
        append_df(obj)
        return rows

    if isinstance(obj, dict):
        inner = obj.get(strategy_name) if strategy_name in obj and isinstance(obj[strategy_name], dict) else obj
        if isinstance(inner, dict):
            for pair, v in inner.items():
                if hasattr(v, "iterrows"):
                    append_df(v, str(pair))
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            if "pair" not in item:
                                item["pair"] = str(pair)
                            rows.append(item)
    return rows


def _estimate_rejected_outcome(
    pair: str,
    ts_value: Any,
    index_map: dict[str, dict[str, Any]],
    horizon: int,
) -> dict[str, Any] | None:
    sr, pos = _find_signal_row(index_map, pair, ts_value)
    if sr is None:
        return None

    entry_price = _to_float(sr.get("close"), 0.0)
    if entry_price <= 0:
        return None

    idx = index_map.get(pair) or index_map.get("*")
    if not idx:
        return None
    rows_list: list[Any] = idx["rows"]
    end_pos = min(len(rows_list), pos + max(1, horizon))
    window = rows_list[pos:end_pos]
    if not window:
        return None

    lows = [_to_float(x.get("low"), _to_float(x.get("close"), entry_price)) for x in window]
    highs = [_to_float(x.get("high"), _to_float(x.get("close"), entry_price)) for x in window]
    close_end = _to_float(window[-1].get("close"), entry_price)

    min_low = min(lows) if lows else entry_price
    max_high = max(highs) if highs else entry_price
    potential_profit_ratio = _safe_div(entry_price - min_low, entry_price)  # short opportunity
    adverse_ratio = _safe_div(entry_price - max_high, entry_price)  # negative if adverse
    hypothetical_ratio = _safe_div(entry_price - close_end, entry_price)

    return {
        "entry_price": entry_price,
        "min_low": min_low,
        "max_high": max_high,
        "potential_profit_ratio": potential_profit_ratio,
        "adverse_ratio": adverse_ratio,
        "hypothetical_ratio": hypothetical_ratio,
        "is_win": 1 if hypothetical_ratio > 0 else 0,
    }


def analyze_rejected_trades(
    artifacts: RunArtifacts,
    strategy_name: str,
    index_map: dict[str, dict[str, Any]],
    trade_rows: list[dict[str, Any]],
    timeframe: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rejected_rows = _load_rejected_rows(artifacts.rejected_path, strategy_name)
    if not rejected_rows:
        return {
            "rejected_total": 0,
            "rejected_winrate_pct": 0.0,
            "rejected_avg_hypothetical_pct": 0.0,
            "executed_winrate_pct": round(_pct(_safe_div(sum(1 for t in trade_rows if _to_float(t.get("profit_ratio"), 0.0) > 0), len(trade_rows))), 4) if trade_rows else 0.0,
            "executed_avg_profit_pct": round(_pct(statistics.mean([_to_float(t.get("profit_ratio"), 0.0) for t in trade_rows]) if trade_rows else 0.0), 4),
            "opportunity_cost_abs": 0.0,
        }, []

    avg_duration = statistics.mean([_to_float(r.get("duration_min"), 0.0) for r in trade_rows]) if trade_rows else 240.0
    tf_minutes = _timeframe_to_minutes(timeframe)
    horizon = max(1, int(round(avg_duration / max(tf_minutes, 1))))
    avg_stake = statistics.mean([_to_float(r.get("stake_amount"), 0.0) for r in trade_rows if _to_float(r.get("stake_amount"), 0.0) > 0]) if trade_rows else 0.0

    analyzed: list[dict[str, Any]] = []
    for item in rejected_rows:
        pair = str(item.get("pair") or "")
        ts_value = item.get("date") or item.get("timestamp") or item.get("open_date")
        est = _estimate_rejected_outcome(pair, ts_value, index_map, horizon)
        if est is None:
            continue
        reason = str(item.get("reason") or item.get("rejection_reason") or item.get("exit_reason") or "")
        analyzed.append(
            {
                "pair": pair,
                "timestamp": _as_iso(ts_value),
                "reason": reason,
                "blocked_by_max_open_trades": 1 if ("max_open" in reason.lower() or "open trade" in reason.lower()) else 0,
                "blocked_by_protection": 1 if "protection" in reason.lower() else 0,
                "blocked_by_cooldown": 1 if "cooldown" in reason.lower() else 0,
                "blocked_by_pairlist": 1 if "pairlist" in reason.lower() else 0,
                "blocked_by_volume_filter": 1 if "volume" in reason.lower() else 0,
                "entry_price": round(est["entry_price"], 8),
                "potential_profit_pct": round(_pct(est["potential_profit_ratio"]), 4),
                "adverse_pct": round(_pct(est["adverse_ratio"]), 4),
                "hypothetical_profit_pct": round(_pct(est["hypothetical_ratio"]), 4),
                "is_win": est["is_win"],
                "opportunity_cost_abs": round(est["hypothetical_ratio"] * avg_stake, 8),
            }
        )

    rejected_ratios = [_to_float(r.get("hypothetical_profit_pct"), 0.0) / 100.0 for r in analyzed]
    executed_ratios = [_to_float(t.get("profit_ratio"), 0.0) for t in trade_rows]
    summary = {
        "rejected_total": len(analyzed),
        "rejected_winrate_pct": round(_pct(_safe_div(sum(1 for r in analyzed if int(r.get("is_win", 0)) == 1), len(analyzed))), 4) if analyzed else 0.0,
        "rejected_avg_hypothetical_pct": round(_pct(statistics.mean(rejected_ratios) if rejected_ratios else 0.0), 4),
        "executed_total": len(trade_rows),
        "executed_winrate_pct": round(_pct(_safe_div(sum(1 for x in executed_ratios if x > 0), len(executed_ratios))), 4) if executed_ratios else 0.0,
        "executed_avg_profit_pct": round(_pct(statistics.mean(executed_ratios) if executed_ratios else 0.0), 4),
        "opportunity_cost_abs": round(sum(_to_float(r.get("opportunity_cost_abs"), 0.0) for r in analyzed), 8),
    }
    return summary, analyzed


def correlate_market_condition(
    trade_rows: list[dict[str, Any]],
    market_change_path: str | None,
    timeframe: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    if not market_change_path or not os.path.exists(market_change_path):
        return {"status": "market_change.feather not found"}, [], []

    try:
        import pandas as pd  # type: ignore
    except Exception:
        return {"status": "pandas not available"}, [], []

    try:
        market_df = pd.read_feather(market_change_path)
    except Exception as e:
        return {"status": f"failed to read market_change.feather: {e}"}, [], []

    if market_df.empty or "date" not in market_df.columns:
        return {"status": "market_change data empty or missing date"}, [], []

    market_df = market_df.copy()
    market_df["date"] = pd.to_datetime(market_df["date"], utc=True, errors="coerce")
    market_df = market_df.dropna(subset=["date"]).sort_values("date")
    market_df["mean"] = pd.to_numeric(market_df.get("mean"), errors="coerce")
    if market_df["mean"].isna().all():
        return {"status": "market_change.mean unavailable"}, [], []

    tf_minutes = _timeframe_to_minutes(timeframe)
    periods_24h = max(1, int(round(1440 / max(tf_minutes, 1))))
    market_df["chg_24h"] = market_df["mean"] / market_df["mean"].shift(periods_24h) - 1.0

    def label_regime(value: float) -> str:
        if value >= 0.05:
            return "rally"
        if value <= -0.03:
            return "downtrend"
        return "range"

    market_df["market_regime"] = market_df["chg_24h"].apply(lambda v: label_regime(_to_float(v, 0.0)))

    trades_df = pd.DataFrame(trade_rows)
    if trades_df.empty:
        return {"status": "no trades"}, [], []

    trades_df["open_date_utc"] = pd.to_datetime(trades_df["open_date_utc"], utc=True, errors="coerce")
    trades_df = trades_df.dropna(subset=["open_date_utc"]).sort_values("open_date_utc")

    merged = pd.merge_asof(
        trades_df,
        market_df[["date", "chg_24h", "market_regime"]].sort_values("date"),
        left_on="open_date_utc",
        right_on="date",
        direction="backward",
    )

    merged["profit_ratio"] = pd.to_numeric(merged.get("profit_ratio"), errors="coerce").fillna(0.0)
    merged["is_win"] = (merged["profit_ratio"] > 0).astype(int)
    grouped = merged.groupby("market_regime", dropna=False)

    regime_rows: list[dict[str, Any]] = []
    for regime, g in grouped:
        ratios = g["profit_ratio"].tolist()
        regime_rows.append(
            {
                "market_regime": str(regime),
                "trades": int(len(g)),
                "winrate_pct": round(_pct(_safe_div(int(g["is_win"].sum()), len(g))), 4) if len(g) > 0 else 0.0,
                "avg_profit_pct": round(_pct(statistics.mean(ratios) if ratios else 0.0), 4),
            }
        )

    summary = {
        "status": "ok",
        "periods_24h": periods_24h,
        "rally_winrate_pct": next((r["winrate_pct"] for r in regime_rows if r["market_regime"] == "rally"), 0.0),
        "range_winrate_pct": next((r["winrate_pct"] for r in regime_rows if r["market_regime"] == "range"), 0.0),
        "downtrend_winrate_pct": next((r["winrate_pct"] for r in regime_rows if r["market_regime"] == "downtrend"), 0.0),
    }
    trade_regime_rows: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        trade_regime_rows.append(
            {
                "trade_id": row.get("trade_id"),
                "pair": row.get("pair"),
                "open_date_utc": row.get("open_date_utc").isoformat() if hasattr(row.get("open_date_utc"), "isoformat") else str(row.get("open_date_utc") or ""),
                "market_regime": row.get("market_regime"),
                "market_change_24h_pct": round(_pct(_to_float(row.get("chg_24h"), 0.0)), 6),
            }
        )
    return summary, regime_rows, trade_regime_rows


def analyze_gate_filter_funnel(
    signal_index: dict[str, dict[str, Any]],
    horizon: int,
    drop_threshold: float = 0.01,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair, payload in signal_index.items():
        ts_list: list[int] = payload["ts"]
        sr_list: list[Any] = payload["rows"]
        if not sr_list:
            continue

        sample = sr_list[0]
        if not hasattr(sample, "index"):
            continue
        dbg_cols = [c for c in sample.index.tolist() if isinstance(c, str) and c.startswith("dbg_")]
        if not dbg_cols:
            continue

        close_arr = [_to_float(x.get("close"), 0.0) for x in sr_list]
        low_arr = [_to_float(x.get("low"), _to_float(x.get("close"), 0.0)) for x in sr_list]

        for col in dbg_cols:
            trigger_count = 0
            blocked_count = 0
            wrong_filtered = 0
            for i, sr in enumerate(sr_list):
                val = _to_int(sr.get(col), 0)
                if val == 1:
                    trigger_count += 1
                    continue
                blocked_count += 1
                entry = close_arr[i]
                if entry <= 0:
                    continue
                end = min(len(sr_list), i + max(1, horizon))
                future_min = min(low_arr[i:end]) if end > i else low_arr[i]
                short_drop = _safe_div(entry - future_min, entry)
                if short_drop >= drop_threshold:
                    wrong_filtered += 1

            total = trigger_count + blocked_count
            blocking_rate = _safe_div(blocked_count, total)
            wrong_rate = _safe_div(wrong_filtered, blocked_count) if blocked_count > 0 else 0.0
            filtering_precision = 1.0 - wrong_rate
            rows.append(
                {
                    "pair": pair,
                    "filter": col,
                    "samples": total,
                    "trigger_rate_pct": round(_pct(_safe_div(trigger_count, total)), 4) if total > 0 else 0.0,
                    "blocking_rate_pct": round(_pct(blocking_rate), 4),
                    "wrong_filtered_rate_pct": round(_pct(wrong_rate), 4),
                    "filtering_precision_pct": round(_pct(filtering_precision), 4),
                }
            )

    # aggregate by filter across pairs
    agg: dict[str, dict[str, float]] = {}
    for r in rows:
        f = str(r["filter"])
        g = agg.setdefault(f, {"samples": 0.0, "trigger": 0.0, "blocked": 0.0, "wrong": 0.0})
        s = _to_float(r.get("samples"), 0.0)
        g["samples"] += s
        g["trigger"] += s * (_to_float(r.get("trigger_rate_pct"), 0.0) / 100.0)
        g["blocked"] += s * (_to_float(r.get("blocking_rate_pct"), 0.0) / 100.0)
        g["wrong"] += s * (_to_float(r.get("wrong_filtered_rate_pct"), 0.0) / 100.0)

    out: list[dict[str, Any]] = []
    for f, g in sorted(agg.items(), key=lambda x: x[0]):
        blocked = g["blocked"]
        wrong_rate = _safe_div(g["wrong"], blocked) if blocked > 0 else 0.0
        out.append(
            {
                "filter": f,
                "samples": int(round(g["samples"])),
                "trigger_rate_pct": round(_pct(_safe_div(g["trigger"], g["samples"])), 4) if g["samples"] > 0 else 0.0,
                "blocking_rate_pct": round(_pct(_safe_div(g["blocked"], g["samples"])), 4) if g["samples"] > 0 else 0.0,
                "wrong_filtered_rate_pct": round(_pct(wrong_rate), 4),
                "filtering_precision_pct": round(_pct(1.0 - wrong_rate), 4),
            }
        )
    return out


def _ascii_histogram(values: list[float], bins: int = 8, width: int = 18) -> list[str]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi == lo:
        return [f"{lo:.2f}% | {'#' * width} ({len(values)})"]
    step = (hi - lo) / bins
    counts = [0 for _ in range(bins)]
    for v in values:
        idx = min(bins - 1, int((v - lo) / step))
        counts[idx] += 1
    mx = max(counts) if counts else 1
    lines: list[str] = []
    for i, c in enumerate(counts):
        left = lo + i * step
        right = left + step
        bar = "#" * max(1, int(round((c / mx) * width))) if c > 0 else ""
        lines.append(f"{left:.2f}%..{right:.2f}% | {bar} ({c})")
    return lines


def _build_deep_diagnostics(
    trade_rows: list[dict[str, Any]],
    rejected_summary: dict[str, Any],
    market_summary: dict[str, Any],
    market_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    maes = [_pct(_to_float(t.get("mae_ratio"), 0.0), 4) for t in trade_rows]
    mfes = [_pct(_to_float(t.get("mfe_ratio"), 0.0), 4) for t in trade_rows]
    winners = [t for t in trade_rows if _to_float(t.get("profit_ratio"), 0.0) > 0]
    giveback = []
    for t in winners:
        mfe = _to_float(t.get("mfe_ratio"), 0.0)
        realized = _to_float(t.get("profit_ratio"), 0.0)
        if mfe > 0:
            giveback.append(max(0.0, 1.0 - _safe_div(realized, mfe)))

    insights: list[str] = []
    avg_mae = statistics.mean(maes) if maes else 0.0
    avg_mfe = statistics.mean(mfes) if mfes else 0.0
    if avg_mae > 3.0:
        insights.append(
            f"Pain Point A: Avg MAE is {avg_mae:.2f}%, stoploss pressure is high; consider tighter entry filters or risk cap near 3.5%."
        )
    if _to_float(rejected_summary.get("rejected_avg_hypothetical_pct"), 0.0) > _to_float(rejected_summary.get("executed_avg_profit_pct"), 0.0):
        insights.append(
            "Pain Point B: Rejected trades show better hypothetical average return than executed trades, max_open_trades may be locking capital in lower-quality positions."
        )
    if market_summary.get("status") == "ok":
        rally_wr = _to_float(market_summary.get("rally_winrate_pct"), 0.0)
        down_wr = _to_float(market_summary.get("downtrend_winrate_pct"), 0.0)
        if rally_wr < down_wr:
            insights.append(
                f"Pain Point C: Win rate in rally regime ({rally_wr:.2f}%) is weaker than downtrend regime ({down_wr:.2f}%), strategy is vulnerable during broad market pumps."
            )

    return {
        "mae_mfe": {
            "avg_mae_pct": round(statistics.mean(maes) if maes else 0.0, 4),
            "avg_mfe_pct": round(statistics.mean(mfes) if mfes else 0.0, 4),
            "profit_giveback_pct": round(_pct(statistics.mean(giveback) if giveback else 0.0), 4),
            "mae_hist": _ascii_histogram(maes),
            "mfe_hist": _ascii_histogram(mfes),
        },
        "rejected_vs_executed": rejected_summary,
        "market_condition": {
            "summary": market_summary,
            "rows": market_rows,
        },
        "gate_filter_funnel": gate_rows,
        "insights": insights,
    }


def _build_signal_context_and_regime(
    trade_rows: list[dict[str, Any]],
    signal_index: dict[str, dict[str, Any]],
    strategy_name: str,
    strategy_data: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not signal_index:
        return [], []

    context_rows: list[dict[str, Any]] = []
    regime_raw: list[dict[str, Any]] = []
    minimal_roi = {}
    if isinstance(strategy_data, dict):
        minimal_roi = strategy_data.get("minimal_roi") if isinstance(strategy_data.get("minimal_roi"), dict) else {}
    roi_target = _to_float(minimal_roi.get("0"), 0.0) if minimal_roi else 0.0
    stoploss_ratio = _to_float(strategy_data.get("stoploss"), 0.0) if isinstance(strategy_data, dict) else 0.0

    for trade in trade_rows:
        trade_id = trade.get("trade_id")
        pair = str(trade.get("pair") or "")

        event_seq = 0
        for event_name, ts_key in (("entry", "open_date_utc"), ("exit", "close_date_utc")):
            event_seq += 1
            sr, _ = _find_signal_row(signal_index, pair, trade.get(ts_key))
            if sr is None:
                continue

            close_v = _to_float(sr.get("close"), 0.0)
            atr_v = _to_float(sr.get("atr"), 0.0)
            ma_fast = _to_float(sr.get("ma7"), 0.0)
            ma_slow = _to_float(sr.get("ma25"), 0.0)
            ma200 = _to_float(sr.get("ma200"), _to_float(sr.get("ma99"), 0.0))

            dbg_cols = [c for c in sr.index.tolist() if isinstance(c, str) and c.startswith("dbg_")]
            entry_flags = {}
            for i, c in enumerate(sorted(dbg_cols)[:8], start=1):
                entry_flags[f"entry_condition_{i}"] = _to_int(sr.get(c), 0)

            exit_reason = str(trade.get("exit_reason", ""))
            direction = str(trade.get("direction", "long"))
            open_rate = _to_float(trade.get("open_rate"), 0.0)
            price_for_distance = close_v if close_v > 0 else _to_float(trade.get("close_rate"), 0.0)
            stop_price = 0.0
            roi_price = 0.0
            if open_rate > 0:
                if direction == "short":
                    stop_price = open_rate * (1.0 - stoploss_ratio)
                    roi_price = open_rate * (1.0 - roi_target) if roi_target > 0 else open_rate
                else:
                    stop_price = open_rate * (1.0 + stoploss_ratio)
                    roi_price = open_rate * (1.0 + roi_target) if roi_target > 0 else open_rate

            row = {
                "trade_id": trade_id,
                "event_seq": event_seq,
                "pair": pair,
                "timestamp": _as_iso(trade.get(ts_key)),
                "event": event_name,
                "close": close_v,
                "volume": _to_float(sr.get("volume"), 0.0),
                "spread": _to_float(sr.get("spread"), 0.0),
                "atr": atr_v,
                "atr_pct": round(_pct(_safe_div(atr_v, close_v), 6), 6) if close_v > 0 else 0.0,
                "rsi": _to_float(sr.get("rsi"), 0.0),
                "stoch": _to_float(sr.get("stoch"), 0.0),
                "mfi": _to_float(sr.get("mfi"), 0.0),
                "ma_fast": ma_fast,
                "ma_slow": ma_slow,
                "ma200": ma200,
                "slope_fast": _to_float(sr.get("ma7_diff"), 0.0),
                "slope_slow": _to_float(sr.get("ma25_diff"), 0.0),
                "volatility_regime_metric": _to_float(sr.get("atr_ratio"), 0.0),
                "mean_reversion_distance": _to_float(sr.get("zscore"), 0.0),
                "enter_tag": trade.get("enter_tag", ""),
                "exit_reason": exit_reason,
                "exit_roi_hit": 1 if event_name == "exit" and "roi" in exit_reason.lower() else 0,
                "exit_stoploss_hit": 1 if event_name == "exit" and "stop" in exit_reason.lower() else 0,
                "exit_trailing_hit": 1 if event_name == "exit" and "trail" in exit_reason.lower() else 0,
                "exit_custom_exit_hit": 1 if event_name == "exit" and ("custom" in exit_reason.lower() or "signal" in exit_reason.lower()) else 0,
                "exit_force_exit": 1 if event_name == "exit" and ("force" in exit_reason.lower() or "emergency" in exit_reason.lower()) else 0,
                "current_profit_ratio": _to_float(trade.get("profit_ratio"), 0.0) if event_name == "exit" else "",
                "trade_duration_min": _to_float(trade.get("duration_min"), 0.0) if event_name == "exit" else "",
                "distance_to_stoploss_ratio": round(_safe_div(price_for_distance - stop_price, open_rate), 8) if event_name == "exit" and open_rate > 0 else "",
                "distance_to_roi_ratio": round(_safe_div(roi_price - price_for_distance, open_rate), 8) if event_name == "exit" and open_rate > 0 else "",
                **entry_flags,
            }
            context_rows.append(row)

            if event_name == "entry":
                regime_raw.append(
                    {
                        "pair": pair,
                        "trade_id": trade.get("trade_id"),
                        "profit_abs": _to_float(trade.get("profit_abs"), 0.0),
                        "profit_ratio": _to_float(trade.get("profit_ratio"), 0.0),
                        "trend_bin": "above_ma200" if ma200 > 0 and close_v > ma200 else "below_ma200",
                        "atr_pct": _safe_div(atr_v, close_v) if close_v > 0 else 0.0,
                    }
                )

    if not regime_raw:
        return context_rows, []

    atr_values = sorted([r["atr_pct"] for r in regime_raw])
    q50 = _percentile(atr_values, 50)

    bin_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in regime_raw:
        vol_bin = "high_volatility" if row["atr_pct"] >= q50 else "low_volatility"
        key = (row["trend_bin"], vol_bin)
        bin_groups.setdefault(key, []).append(row)

    regime_rows: list[dict[str, Any]] = []
    for (trend_bin, vol_bin), rows in sorted(bin_groups.items()):
        profits = [r["profit_abs"] for r in rows]
        ratios = [r["profit_ratio"] for r in rows]
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p < 0]
        regime_rows.append(
            {
                "trend_regime": trend_bin,
                "volatility_regime": vol_bin,
                "trades": len(rows),
                "expectancy_pct": round(_pct(statistics.mean(ratios) if ratios else 0.0), 4),
                "profit_factor": round(_safe_div(sum(wins), abs(sum(losses))), 8) if losses else 0.0,
                "max_dd_proxy_pct": round(_pct(abs(min(ratios)) if ratios else 0.0), 4),
                "net_pnl": round(sum(profits), 8),
            }
        )

    return context_rows, regime_rows


def _export_run_report(
    stem: str,
    strategy_name: str,
    artifacts: RunArtifacts,
    strategy_data: dict[str, Any],
    trade_rows: list[dict[str, Any]],
) -> tuple[str, list[str], dict[str, Any], dict[str, Any]]:
    report_dir = os.path.join(REPORTS_DIR, stem)
    if os.path.exists(report_dir):
        shutil.rmtree(report_dir)
    _ensure_dir(report_dir)

    meta_data = _safe_read_json(artifacts.meta_path) if artifacts.meta_path else None
    signal_index = _build_signal_index(artifacts.signals_path, strategy_name)
    _enrich_trades_with_market_context(trade_rows, signal_index)

    starting_balance = _to_float(strategy_data.get("starting_balance"), 0.0)
    equity_rows, daily_rows = _build_equity_and_daily(trade_rows, starting_balance)
    summary = _build_summary(trade_rows, equity_rows, daily_rows, strategy_data)
    pair_breakdown = _build_pair_breakdown(trade_rows)
    entry_exit_reason = _build_entry_exit_reason(trade_rows)
    time_breakdown = _build_time_breakdown(trade_rows)
    cost_impact = _build_cost_impact(trade_rows, starting_balance)
    signal_context, regime_bins = _build_signal_context_and_regime(
        trade_rows,
        signal_index,
        strategy_name,
        strategy_data,
    )
    timeframe = str(strategy_data.get("timeframe") or "15m")
    rejected_summary, rejected_rows = analyze_rejected_trades(
        artifacts=artifacts,
        strategy_name=strategy_name,
        index_map=signal_index,
        trade_rows=trade_rows,
        timeframe=timeframe,
    )
    market_summary, market_rows, trade_regime_rows = correlate_market_condition(
        trade_rows=trade_rows,
        market_change_path=artifacts.market_change_path,
        timeframe=timeframe,
    )
    regime_by_trade_id = {str(r.get("trade_id")): r.get("market_regime", "") for r in trade_regime_rows}
    for row in trade_rows:
        row["trade_regime"] = regime_by_trade_id.get(str(row.get("trade_id")), "")
    avg_duration = statistics.mean([_to_float(r.get("duration_min"), 0.0) for r in trade_rows]) if trade_rows else 240.0
    horizon = max(1, int(round(avg_duration / max(_timeframe_to_minutes(timeframe), 1))))
    gate_funnel_rows = analyze_gate_filter_funnel(signal_index, horizon=horizon)
    diagnostics = _build_deep_diagnostics(
        trade_rows=trade_rows,
        rejected_summary=rejected_summary,
        market_summary=market_summary,
        market_rows=market_rows,
        gate_rows=gate_funnel_rows,
    )

    strategy_file, _ = _read_strategy_code(strategy_name)
    run_id = ""
    if isinstance(meta_data, dict):
        section = meta_data.get(strategy_name)
        if isinstance(section, dict):
            run_id = str(section.get("run_id", ""))

    run_meta = {
        "run_id": run_id,
        "strategy_name": strategy_name,
        "strategy_file_path": strategy_file or "",
        "strategy_file_hash": _hash_file(strategy_file),
        "timeframe": strategy_data.get("timeframe", "N/A"),
        "timeframe_detail": strategy_data.get("timeframe_detail", "N/A"),
        "timerange": TIMERANGE,
        "stake_currency": strategy_data.get("stake_currency", "N/A"),
        "stake_amount": strategy_data.get("stake_amount", "N/A"),
        "starting_balance": strategy_data.get("starting_balance", "N/A"),
        "max_open_trades": strategy_data.get("max_open_trades_setting", strategy_data.get("max_open_trades", "N/A")),
        "position_adjustment_enable": strategy_data.get("position_adjustment_enable", "N/A"),
        "leverage": strategy_data.get("leverage", "N/A"),
        "fee": strategy_data.get("fee", "N/A"),
        "maker_fee": strategy_data.get("maker_fee", "N/A"),
        "taker_fee": strategy_data.get("taker_fee", "N/A"),
        "order_types": strategy_data.get("order_types", "N/A"),
        "order_time_in_force": strategy_data.get("order_time_in_force", "N/A"),
        "minimal_roi": strategy_data.get("minimal_roi", "N/A"),
        "stoploss": strategy_data.get("stoploss", "N/A"),
        "trailing_stop": strategy_data.get("trailing_stop", "N/A"),
        "trailing_stop_positive": strategy_data.get("trailing_stop_positive", "N/A"),
        "trailing_stop_positive_offset": strategy_data.get("trailing_stop_positive_offset", "N/A"),
        "trailing_only_offset_is_reached": strategy_data.get("trailing_only_offset_is_reached", "N/A"),
        "custom_exit": strategy_data.get("use_exit_signal", "N/A"),
        "protections_enabled": strategy_data.get("enable_protections", "N/A"),
        "protections": strategy_data.get("protections", "N/A"),
        "pairlist": strategy_data.get("pairlist", "N/A"),
        "whitelist": strategy_data.get("whitelist", "N/A"),
        "blacklist": strategy_data.get("blacklist", "N/A"),
        "trading_mode": strategy_data.get("trading_mode", "N/A"),
        "margin_mode": strategy_data.get("margin_mode", "N/A"),
        "slippage_assumption": "0 (baseline); see cost_impact.csv scenarios",
        "exchange": strategy_data.get("exchange", "N/A"),
        "pairs_method": strategy_data.get("pairs", "N/A"),
        "git_commit_hash": _git_commit_hash(),
        "freqtrade_version": strategy_data.get("freqtrade_version", "N/A"),
        "backtest_json": artifacts.json_path or "",
        "signals_path": artifacts.signals_path or "",
        "rejected_path": artifacts.rejected_path or "",
        "market_change_path": artifacts.market_change_path or "",
        "meta_path": artifacts.meta_path or "",
        "config_path": artifacts.config_path or "",
    }
    config_data = _safe_read_json(artifacts.config_path) if artifacts.config_path else None
    if isinstance(config_data, dict):
        run_meta["config_snapshot"] = {
            "exchange": config_data.get("exchange", run_meta.get("exchange")),
            "stake_currency": config_data.get("stake_currency", run_meta.get("stake_currency")),
            "stake_amount": config_data.get("stake_amount", run_meta.get("stake_amount")),
            "max_open_trades": config_data.get("max_open_trades", run_meta.get("max_open_trades")),
            "order_types": config_data.get("order_types", run_meta.get("order_types")),
            "order_time_in_force": config_data.get("order_time_in_force", run_meta.get("order_time_in_force")),
            "pairlists": config_data.get("pairlists", run_meta.get("pairlist")),
            "protections": config_data.get("protections", run_meta.get("protections")),
        }
        if "strategy_parameters" in config_data:
            run_meta["custom_parameters"] = config_data.get("strategy_parameters")

    outputs: list[str] = []

    summary_path = os.path.join(report_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    outputs.append(summary_path)

    run_meta_path = os.path.join(report_dir, "run_metadata.json")
    with open(run_meta_path, "w", encoding="utf-8") as f:
        json.dump(run_meta, f, indent=2, ensure_ascii=False)
    outputs.append(run_meta_path)

    trades_path = os.path.join(report_dir, "trades.csv")
    _write_csv(trades_path, [
        "trade_id", "pair", "direction", "timeframe", "open_time", "close_time",
        "open_date_utc", "close_date_utc", "duration_min", "open_rate", "close_rate",
        "min_rate", "max_rate",
        "trade_regime",
        "stake_amount", "amount", "profit_abs", "profit_ratio", "profit_pct",
        "max_profit_ratio", "max_drawdown_ratio", "mfe_ratio", "mae_ratio", "entry_efficiency_score", "mfe_price", "mae_price", "mfe_ts", "mae_ts",
        "fee_open", "fee_close", "fee_total",
        "entry_spread", "exit_spread", "slippage_entry", "slippage_exit", "slippage_est",
        "expected_fill_price_entry", "expected_fill_price_exit", "assumed_fill_price_entry", "assumed_fill_price_exit",
        "enter_tag", "exit_reason", "exit_tag", "stop_loss_hit",
        "roi_hit", "trailing_stop_hit", "protection_blocked"
    ], trade_rows)
    outputs.append(trades_path)

    equity_path = os.path.join(report_dir, "equity_curve.csv")
    _write_csv(equity_path, ["index", "timestamp", "trade_id", "pair", "pnl_abs", "pnl_pct", "equity", "drawdown_pct"], equity_rows)
    outputs.append(equity_path)

    daily_path = os.path.join(report_dir, "daily_pnl.csv")
    _write_csv(daily_path, ["date", "pnl_abs", "pnl_pct", "equity", "drawdown_pct"], daily_rows)
    outputs.append(daily_path)

    pair_path = os.path.join(report_dir, "pair_breakdown.csv")
    _write_csv(pair_path, ["pair", "trades", "winrate_pct", "profit_factor", "net_pnl", "max_drawdown_proxy_pct", "avg_duration_min", "avg_profit_pct", "median_profit_pct"], pair_breakdown)
    outputs.append(pair_path)

    reason_path = os.path.join(report_dir, "entry_exit_reason.csv")
    _write_csv(reason_path, ["enter_tag", "exit_reason", "count", "net_pnl", "avg_pnl", "avg_mfe_pct", "avg_mae_pct"], entry_exit_reason)
    outputs.append(reason_path)

    time_path = os.path.join(report_dir, "time_breakdown.csv")
    _write_csv(time_path, ["weekday", "hour", "trades", "winrate_pct", "expectancy_pct", "pnl_abs", "profit_factor"], time_breakdown)
    outputs.append(time_path)

    cost_path = os.path.join(report_dir, "cost_impact.csv")
    _write_csv(cost_path, ["scenario", "net_profit", "profit_factor", "winrate_pct", "max_drawdown_pct"], cost_impact)
    outputs.append(cost_path)

    regime_path = os.path.join(report_dir, "regime_bins.csv")
    _write_csv(regime_path, ["trend_regime", "volatility_regime", "trades", "expectancy_pct", "profit_factor", "max_dd_proxy_pct", "net_pnl"], regime_bins)
    outputs.append(regime_path)

    market_cond_path = os.path.join(report_dir, "market_condition.csv")
    _write_csv(market_cond_path, ["market_regime", "trades", "winrate_pct", "avg_profit_pct"], market_rows)
    outputs.append(market_cond_path)

    trade_regime_path = os.path.join(report_dir, "trade_regime.csv")
    _write_csv(trade_regime_path, ["trade_id", "pair", "open_date_utc", "market_regime", "market_change_24h_pct"], trade_regime_rows)
    outputs.append(trade_regime_path)

    rejected_path = os.path.join(report_dir, "missed_signals.csv")
    _write_csv(
        rejected_path,
        [
            "pair", "timestamp", "reason",
            "blocked_by_max_open_trades", "blocked_by_protection", "blocked_by_cooldown", "blocked_by_pairlist", "blocked_by_volume_filter",
            "entry_price", "potential_profit_pct", "adverse_pct", "hypothetical_profit_pct", "is_win", "opportunity_cost_abs"
        ],
        rejected_rows,
    )
    outputs.append(rejected_path)

    gate_path = os.path.join(report_dir, "gate_filter_funnel.csv")
    _write_csv(
        gate_path,
        ["filter", "samples", "trigger_rate_pct", "blocking_rate_pct", "wrong_filtered_rate_pct", "filtering_precision_pct"],
        gate_funnel_rows,
    )
    outputs.append(gate_path)

    signal_path = os.path.join(report_dir, "signal_context.csv")
    signal_fields: list[str] = [
        "trade_id", "event_seq", "pair", "timestamp", "event", "close", "volume", "spread", "atr", "atr_pct",
        "rsi", "stoch", "mfi", "ma_fast", "ma_slow", "ma200", "slope_fast", "slope_slow",
        "volatility_regime_metric", "mean_reversion_distance", "enter_tag", "exit_reason",
        "exit_roi_hit", "exit_stoploss_hit", "exit_trailing_hit", "exit_custom_exit_hit", "exit_force_exit",
        "current_profit_ratio", "trade_duration_min", "distance_to_stoploss_ratio", "distance_to_roi_ratio",
    ]
    max_entry_cols = 0
    for row in signal_context:
        cnt = len([k for k in row.keys() if str(k).startswith("entry_condition_")])
        max_entry_cols = max(max_entry_cols, cnt)
    for i in range(1, max_entry_cols + 1):
        signal_fields.append(f"entry_condition_{i}")
    _write_csv(signal_path, signal_fields, signal_context)
    outputs.append(signal_path)

    # Automated sanity checks requested by analyze_backtest_result.md
    entry_counts: dict[str, int] = {}
    exit_counts: dict[str, int] = {}
    for r in signal_context:
        tid = str(r.get("trade_id")) if r.get("trade_id") is not None else ""
        if not tid:
            continue
        if str(r.get("event")) == "entry":
            entry_counts[tid] = entry_counts.get(tid, 0) + 1
        elif str(r.get("event")) == "exit":
            exit_counts[tid] = exit_counts.get(tid, 0) + 1
    entry_ids = set(entry_counts.keys())
    exit_ids = set(exit_counts.keys())
    trade_ids = {str(r.get("trade_id")) for r in trade_rows if r.get("trade_id") is not None}

    non_zero_mfe = sum(1 for r in trade_rows if abs(_to_float(r.get("mfe_ratio"), 0.0)) > 0)
    non_zero_mae = sum(1 for r in trade_rows if abs(_to_float(r.get("mae_ratio"), 0.0)) > 0)
    non_zero_slip = sum(1 for r in trade_rows if abs(_to_float(r.get("slippage_est"), 0.0)) > 0)

    pnl_sum = sum(_to_float(r.get("profit_abs"), 0.0) for r in trade_rows)
    final_equity = _to_float(equity_rows[-1].get("equity"), starting_balance if starting_balance > 0 else 1.0) if equity_rows else (starting_balance if starting_balance > 0 else 1.0)
    initial_equity = starting_balance if starting_balance > 0 else 1.0
    reconcile_delta = (final_equity - initial_equity) - pnl_sum
    mfe_mae_sanity_fail = 0
    mfe_mae_sanity_checked = 0
    for r in trade_rows:
        pr = _to_float(r.get("profit_ratio"), 0.0)
        open_rate = _to_float(r.get("open_rate"), 0.0)
        min_rate = _to_float(r.get("min_rate"), 0.0)
        max_rate = _to_float(r.get("max_rate"), 0.0)
        if open_rate <= 0 or min_rate <= 0 or max_rate <= 0:
            continue
        direction = str(r.get("direction"))
        if direction == "short":
            mfe = _safe_div(open_rate - min_rate, open_rate)
            mae = _safe_div(open_rate - max_rate, open_rate)
        else:
            mfe = _safe_div(max_rate - open_rate, open_rate)
            mae = _safe_div(min_rate - open_rate, open_rate)
        mfe_mae_sanity_checked += 1
        if pr > 0 and mfe + 1e-12 < pr:
            mfe_mae_sanity_fail += 1
        if pr < 0 and mae - 1e-12 > pr:
            mfe_mae_sanity_fail += 1

    validation = {
        "join_integrity": {
            "trade_count": len(trade_ids),
            "entry_event_trade_count": len(entry_ids),
            "exit_event_trade_count": len(exit_ids),
            "entry_join_coverage_pct": round(_pct(_safe_div(len(trade_ids & entry_ids), len(trade_ids))), 4) if trade_ids else 0.0,
            "exit_join_coverage_pct": round(_pct(_safe_div(len(trade_ids & exit_ids), len(trade_ids))), 4) if trade_ids else 0.0,
            "exactly_one_entry_per_trade_pct": round(_pct(_safe_div(sum(1 for k in trade_ids if entry_counts.get(k, 0) == 1), len(trade_ids))), 4) if trade_ids else 0.0,
            "exactly_one_exit_per_trade_pct": round(_pct(_safe_div(sum(1 for k in trade_ids if exit_counts.get(k, 0) == 1), len(trade_ids))), 4) if trade_ids else 0.0,
        },
        "non_zero_check": {
            "mfe_non_zero_count": non_zero_mfe,
            "mae_non_zero_count": non_zero_mae,
            "slippage_non_zero_count": non_zero_slip,
            "mfe_all_zero": non_zero_mfe == 0,
            "mae_all_zero": non_zero_mae == 0,
            "slippage_all_zero": non_zero_slip == 0,
        },
        "totals_reconcile": {
            "sum_trade_profit": round(pnl_sum, 8),
            "equity_delta": round(final_equity - initial_equity, 8),
            "delta_minus_profit": round(reconcile_delta, 10),
            "within_tolerance_1e-6": abs(reconcile_delta) <= 1e-6,
        },
        "mfe_mae_sanity": {
            "checked_count": mfe_mae_sanity_checked,
            "failed_count": mfe_mae_sanity_fail,
            "passed": mfe_mae_sanity_fail == 0,
        },
    }

    validation_path = os.path.join(report_dir, "validation.json")
    with open(validation_path, "w", encoding="utf-8") as f:
        json.dump(validation, f, indent=2, ensure_ascii=False)
    outputs.append(validation_path)

    deep_path = os.path.join(report_dir, "deep_diagnostics.json")
    with open(deep_path, "w", encoding="utf-8") as f:
        json.dump(diagnostics, f, indent=2, ensure_ascii=False)
    outputs.append(deep_path)

    return report_dir, outputs, summary, diagnostics


def _compress_report_dir(report_dir: str) -> str:
    if not os.path.isdir(report_dir):
        raise FileNotFoundError(f"Report directory not found: {report_dir}")

    parent_dir = os.path.dirname(report_dir.rstrip("\\/"))
    stem = os.path.basename(report_dir.rstrip("\\/"))
    zip_path = os.path.join(parent_dir, f"{stem}.zip")

    if os.path.exists(zip_path):
        os.remove(zip_path)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(report_dir):
            for name in files:
                full_path = os.path.join(root, name)
                arcname = os.path.relpath(full_path, report_dir)
                zf.write(full_path, arcname=arcname)

    shutil.rmtree(report_dir)
    return zip_path


def load_last_execution() -> tuple[str, str] | None:
    if not os.path.exists(LAST_RESULT_FILE):
        return None

    with open(LAST_RESULT_FILE, "r", encoding="utf-8-sig", errors="replace") as f:
        data = json.load(f)

    latest_zip = data.get("latest_backtest")
    if isinstance(latest_zip, str) and latest_zip:
        stem = os.path.splitext(os.path.basename(latest_zip))[0]
        strategy_name = data.get("strategy_name", "AMRS3_6Strategy")
        if isinstance(strategy_name, str) and strategy_name:
            return strategy_name, stem

    strategy_name = data.get("strategy_name")
    stem = data.get("stem")
    if isinstance(strategy_name, str) and strategy_name and isinstance(stem, str) and stem:
        return strategy_name, stem

    return None


def main() -> None:
    execution = load_last_execution()
    if not execution:
        print(f"No valid execution result found in: {LAST_RESULT_FILE}")
        print("Run freqtrade_executor.py first.")
        return

    strategy_name, stem = execution

    print("=" * 60)
    print(f"Analyze Backtest Result")
    print(f"Strategy: {strategy_name}")
    print(f"Stem: {stem}")
    print("=" * 60)

    artifacts = resolve_artifacts(stem)
    if artifacts.json_path is None and artifacts.zip_path is None:
        print(f"Error: No artifact found for stem '{stem}'.")
        print(f"Expected at least '{stem}.zip' or '{stem}.json' under: {RESULTS_DIR}")
        return
    if artifacts.json_path is None:
        print(f"Error: Missing backtest json for stem '{stem}'.")
        return

    perf, gate_stats, trades = parse_result(artifacts.json_path, strategy_name, artifacts.signals_path)
    data = _safe_read_json(artifacts.json_path) or {}
    strategy_data = data.get("strategy", {}).get(strategy_name, {}) if isinstance(data.get("strategy"), dict) else {}
    timeframe = str(strategy_data.get("timeframe") or "N/A")
    normalized_trades = _normalize_trades(trades, timeframe)

    chart_paths: list[str] = []
    if (
        EXPORT_TRADE_CHART
        and artifacts.json_path
        and artifacts.signals_path
        and artifacts.signals_path.lower().endswith(".pkl")
    ):
        try:
            chart_out = os.path.join(CHARTS_DIR, f"chart_{stem}_{strategy_name}.png")
            out_path = export_freqtrade_trade_point_chart_png(
                backtest_json_path=artifacts.json_path,
                signals_pkl_path=artifacts.signals_path,
                strategy_name=strategy_name,
                timerange=TIMERANGE,
                output_path=chart_out,
            )
            chart_paths.append(out_path)
        except Exception as e:
            print(f"Chart export failed: {e}")

    report_dir, output_files, summary, diagnostics = _export_run_report(
        stem=stem,
        strategy_name=strategy_name,
        artifacts=artifacts,
        strategy_data=strategy_data if isinstance(strategy_data, dict) else {},
        trade_rows=normalized_trades,
    )
    report_zip = _compress_report_dir(report_dir)

    md = build_backtest_markdown(
        strategy_name=strategy_name,
        timerange=TIMERANGE,
        artifacts=artifacts,
        perf=perf,
        gate_stats=gate_stats,
        diagnostics=diagnostics,
        trades=trades,
        chart_paths=chart_paths,
    )
    pyperclip.copy(md)

    print("\n" + "=" * 60)
    print("Analysis completed. Markdown copied to clipboard.")
    print(f"Report archive: {report_zip}")
    print(f"Removed uncompressed report directory: {report_dir}")
    print(f"Archived artifacts count: {len(output_files)}")
    print(f"Summary trades: {summary.get('total_trades', 0)}")
    print(f"Summary net profit: {summary.get('net_profit', 0)}")
    for p in chart_paths:
        print(f"Chart written: {p}")
    for k in ("Total Trades", "Win Rate", "Profit Total %", "Profit Factor", "Max Drawdown %"):
        if k in perf:
            print(f"{k}: {perf[k]}")
    print("=" * 60)


if __name__ == "__main__":
    main()
