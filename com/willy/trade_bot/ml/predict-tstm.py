from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import torch
from torch import nn


class LSTMClassifier(nn.Module):
    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        num_layers: int,
        dropout: float,
    ) -> None:
        super().__init__()
        lstm_dropout = dropout if num_layers > 1 else 0.0
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=lstm_dropout,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        last_hidden = out[:, -1, :]
        logits = self.fc(self.dropout(last_hidden))
        return logits


def _load_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".pkl", ".pickle"}:
        return pd.read_pickle(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix in {".feather", ".feature"}:
        return pd.read_feather(path)

    load_errors: list[str] = []
    readers = [
        ("feather", pd.read_feather),
        ("pickle", pd.read_pickle),
        ("parquet", pd.read_parquet),
        ("csv", pd.read_csv),
    ]
    for name, reader in readers:
        try:
            return reader(path)
        except Exception as exc:
            load_errors.append(f"{name}: {exc}")
    raise RuntimeError(f"Cannot read input file `{path}`. Details: {' | '.join(load_errors)}")


def _build_feature_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    required_cols = ["open", "high", "low", "close", "vol"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in input data: {missing_cols}")

    frame = df.copy()
    if "start_time" in frame.columns:
        frame["start_time"] = pd.to_datetime(frame["start_time"], errors="coerce", utc=True)

    for col in required_cols:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")

    frame["log_ret_1"] = np.log(frame["close"]).diff(1)
    frame["log_ret_3"] = np.log(frame["close"]).diff(3)
    frame["hl_spread"] = (frame["high"] - frame["low"]) / frame["close"]
    frame["oc_spread"] = (frame["close"] - frame["open"]) / frame["open"]
    frame["vol_change"] = frame["vol"].pct_change().replace([np.inf, -np.inf], np.nan)
    frame["ma8_gap"] = frame["close"] / frame["close"].rolling(8).mean() - 1.0
    frame["ma21_gap"] = frame["close"] / frame["close"].rolling(21).mean() - 1.0
    frame["ret_vol_21"] = frame["log_ret_1"].rolling(21).std()

    feature_cols = [
        "log_ret_1",
        "log_ret_3",
        "hl_spread",
        "oc_spread",
        "vol_change",
        "ma8_gap",
        "ma21_gap",
        "ret_vol_21",
    ]
    frame = frame.dropna(subset=feature_cols).reset_index(drop=True)
    if frame.empty:
        raise ValueError("Feature frame is empty after engineering; provide more historical rows.")
    return frame, feature_cols


def _make_sequences(feature_values: np.ndarray, lookback: int) -> tuple[np.ndarray, np.ndarray]:
    if lookback < 2:
        raise ValueError(f"lookback must be >= 2, got {lookback}")

    xs: list[np.ndarray] = []
    idxs: list[int] = []
    for idx in range(lookback, len(feature_values)):
        xs.append(feature_values[idx - lookback : idx])
        idxs.append(idx)
    if not xs:
        raise ValueError("No sequences created; increase rows or lower lookback.")
    return np.asarray(xs, dtype=np.float32), np.asarray(idxs, dtype=np.int32)


def _select_device(device_arg: str) -> torch.device:
    if device_arg == "cpu":
        return torch.device("cpu")
    if device_arg == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but not available.")
        return torch.device("cuda")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _load_lstm_payload(model_path: Path, device: torch.device) -> dict[str, Any]:
    payload = joblib.load(model_path)
    required = ["torch_state_dict", "feature_columns", "lookback"]
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"Model payload missing keys: {missing}")

    feature_columns = list(payload["feature_columns"])
    lookback = int(payload["lookback"])
    hidden_size = int(payload.get("hidden_size", 64))
    num_layers = int(payload.get("num_layers", 2))
    dropout = float(payload.get("dropout", 0.2))

    model = LSTMClassifier(
        input_size=len(feature_columns),
        hidden_size=hidden_size,
        num_layers=num_layers,
        dropout=dropout,
    ).to(device)

    state_dict_raw = payload["torch_state_dict"]
    state_dict_cpu = {
        key: (value.detach().cpu() if torch.is_tensor(value) else value)
        for key, value in state_dict_raw.items()
    }
    model.load_state_dict(state_dict_cpu)
    model.eval()

    return {
        "model": model,
        "scaler": payload.get("scaler"),
        "feature_columns": feature_columns,
        "lookback": lookback,
        "hidden_size": hidden_size,
        "num_layers": num_layers,
        "dropout": dropout,
    }


def _predict_probabilities(
    model: nn.Module,
    x: np.ndarray,
    batch_size: int,
    device: torch.device,
) -> np.ndarray:
    probs: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(x), batch_size):
            end = start + batch_size
            xb = torch.from_numpy(x[start:end]).float().to(device)
            logits = model(xb)
            pb = torch.softmax(logits, dim=1).cpu().numpy()
            probs.append(pb)
    return np.vstack(probs)


def _build_prediction_frame(
    source_frame: pd.DataFrame,
    seq_indices: np.ndarray,
    probs: np.ndarray,
) -> pd.DataFrame:
    pred_class = np.argmax(probs, axis=1).astype(int)
    signals = np.where(pred_class == 1, "LONG", "SHORT")

    result = pd.DataFrame(
        {
            "pred_class": pred_class,
            "prob_down": probs[:, 0],
            "prob_up": probs[:, 1],
            "signal": signals,
        }
    )

    if "start_time" in source_frame.columns:
        result.insert(0, "start_time", source_frame.loc[seq_indices, "start_time"].to_numpy())
    if "close" in source_frame.columns:
        result.insert(1 if "start_time" in result.columns else 0, "close", source_frame.loc[seq_indices, "close"].to_numpy())
    return result


def _write_batch_output(result_df: pd.DataFrame, output_path: Path, fmt: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        output_path.write_text(result_df.to_json(orient="records", date_format="iso"), encoding="utf-8")
    else:
        result_df.to_csv(output_path, index=False)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LSTM prediction script for sequence_model.joblib")
    parser.add_argument("--model", required=True, help="Path to sequence_model.joblib")
    parser.add_argument("--input", required=True, help="Input OHLCV file (.feature/.feather/.csv/.pkl/.parquet)")
    parser.add_argument("--single", action="store_true", help="Return only the latest prediction")
    parser.add_argument("--output", help="Output path for batch predictions (csv/json)")
    parser.add_argument("--format", choices=["csv", "json"], default="csv", help="Output format for --output")
    parser.add_argument("--batch-size", type=int, default=1024, help="Inference batch size")
    parser.add_argument("--tail-rows", type=int, default=0, help="Use only the last N rows (0 means all)")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto", help="Inference device")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    model_path = Path(args.model)
    input_path = Path(args.input)
    device = _select_device(args.device)

    payload = _load_lstm_payload(model_path, device=device)
    model: nn.Module = payload["model"]
    scaler = payload["scaler"]
    model_feature_cols = payload["feature_columns"]
    lookback = payload["lookback"]

    raw_df = _load_table(input_path)
    if args.tail_rows and args.tail_rows > 0 and len(raw_df) > args.tail_rows:
        raw_df = raw_df.tail(args.tail_rows).reset_index(drop=True)

    feature_frame, computed_feature_cols = _build_feature_frame(raw_df)
    if model_feature_cols != computed_feature_cols:
        raise ValueError(
            "Feature columns mismatch between model and data pipeline. "
            f"model={model_feature_cols}, computed={computed_feature_cols}"
        )

    feature_values = feature_frame[model_feature_cols].to_numpy(dtype=np.float32)
    if scaler is None:
        raise ValueError("Model payload does not contain scaler; cannot normalize input.")
    feature_values = scaler.transform(feature_values).astype(np.float32)

    x_seq, seq_indices = _make_sequences(feature_values, lookback=lookback)
    probs = _predict_probabilities(model=model, x=x_seq, batch_size=args.batch_size, device=device)
    prediction_df = _build_prediction_frame(feature_frame, seq_indices, probs)

    if args.single:
        latest = prediction_df.iloc[-1].to_dict()
        latest["model_path"] = str(model_path)
        latest["lookback"] = lookback
        latest["device"] = str(device)
        print(json.dumps(latest, ensure_ascii=False, default=str))
        return

    if args.output:
        output_path = Path(args.output)
        _write_batch_output(prediction_df, output_path=output_path, fmt=args.format)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "rows": int(len(prediction_df)),
                    "output_path": str(output_path),
                    "format": args.format,
                },
                ensure_ascii=False,
            )
        )
        return

    print(prediction_df.tail(20).to_string(index=False))
    print(f"\nTotal prediction rows: {len(prediction_df)}")


if __name__ == "__main__":
    main()
