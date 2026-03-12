import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler

# Ensure UTF-8 encoding for Windows consoles
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


class MLService:
    """
    通用機器學習服務，提供資料預處理、時序切分、標準化與報告生成等基礎功能。
    這些邏輯與具體交易策略無關，可供多個模型訓練器共用。
    """

    @staticmethod
    def make_log_returns(df: pd.DataFrame, price_col: str = "close") -> pd.DataFrame:
        """計算對數收益率"""
        if df is None or df.empty:
            return df
        df = df.copy()
        df["log_return"] = np.log(df[price_col] / df[price_col].shift(1))
        return df

    @staticmethod
    def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
        """安全的除法處理，防止除以零或產生 inf"""
        denominator = denominator.replace(0, np.nan)
        return (numerator / denominator).replace([np.inf, -np.inf], np.nan)

    def time_series_split_5way(
            self,
            X: pd.DataFrame,
            Y: pd.Series,
            train_ratio: float = 0.60,
            val_earlystop_ratio: float = 0.10,
            val_calibration_ratio: float = 0.10,
            val_threshold_ratio: float = 0.10,
            gap: int = 20,
    ):
        """
        標準金融時序 5 段切分框架:
        Train -> gap -> Val(EarlyStop) -> gap -> Val(Calib) -> gap -> Val(Thres) -> gap -> Test
        """
        if X is None or X.empty or Y is None or Y.empty:
            raise ValueError("Input X or Y is empty.")
        if len(X) != len(Y):
            raise ValueError(f"X/Y length mismatch: {len(X)} vs {len(Y)}")

        n = len(X)
        n_train = int(n * train_ratio)
        n_val_early = int(n * val_earlystop_ratio)
        n_val_cal = int(n * val_calibration_ratio)
        n_val_th = int(n * val_threshold_ratio)

        train_end = n_train
        val_early_start = train_end + gap
        val_early_end = val_early_start + n_val_early
        val_cal_start = val_early_end + gap
        val_cal_end = val_cal_start + n_val_cal
        val_th_start = val_cal_end + gap
        val_th_end = val_th_start + n_val_th
        test_start = val_th_end + gap

        if test_start >= n:
            raise ValueError(f"Dataset too small (n={n}) for 5-way split with gap={gap}")

        return (
            X.iloc[:train_end], X.iloc[val_early_start:val_early_end],
            X.iloc[val_cal_start:val_cal_end], X.iloc[val_th_start:val_th_end],
            X.iloc[test_start:],
            Y.iloc[:train_end], Y.iloc[val_early_start:val_early_end],
            Y.iloc[val_cal_start:val_cal_end], Y.iloc[val_th_start:val_th_end],
            Y.iloc[test_start:]
        )

    def normalize_features_5way(
            self,
            X_train: pd.DataFrame,
            X_val_early: pd.DataFrame,
            X_val_cal: pd.DataFrame,
            X_val_th: pd.DataFrame,
            X_test: pd.DataFrame,
    ):
        """使用 RobustScaler 對 5 段資料進行標準化，確保只在 Train 上 fit"""
        scaler = RobustScaler()
        X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train), columns=X_train.columns, index=X_train.index)
        X_val_early_scaled = pd.DataFrame(scaler.transform(X_val_early), columns=X_val_early.columns,
                                          index=X_val_early.index)
        X_val_cal_scaled = pd.DataFrame(scaler.transform(X_val_cal), columns=X_val_cal.columns, index=X_val_cal.index)
        X_val_th_scaled = pd.DataFrame(scaler.transform(X_val_th), columns=X_val_th.columns, index=X_val_th.index)
        X_test_scaled = pd.DataFrame(scaler.transform(X_test), columns=X_test.columns, index=X_test.index)

        return X_train_scaled, X_val_early_scaled, X_val_cal_scaled, X_val_th_scaled, X_test_scaled, scaler

    def export_experiment_report(self, experiment_name: str, walk_forward_df: pd.DataFrame, metadata: dict,
                                 feature_cols: list):
        """
        產出結構化的實驗報告
        """
        report_dir = Path(f"com/willy/trade_bot/ml/generated/experiments/{experiment_name}")
        report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = report_dir / f"report_{timestamp}.md"

        avg_stats = walk_forward_df.mean(numeric_only=True).to_dict()
        feature_summary = f"{', '.join(feature_cols[:5])} ... (Total: {len(feature_cols)})"

        report_content = f"""# 🚀 ML Experiment: {experiment_name}

## 1. Metadata
- **Time**: {datetime.now(timezone.utc).isoformat()}
- **Range**: `{metadata.get('start_dt')}` to `{metadata.get('end_dt')}`
- **Features**: `{feature_summary}`
- **Config**: `lookahead={metadata.get('lookahead')}, atr_mult={metadata.get('atr_multiplier')}`

## 2. Avg Performance
| Metric | Value |
| :--- | :--- |
| **Win Rate** | {avg_stats.get('win_rate', 0):.2%} |
| **Total PnL** | {avg_stats.get('total_pnl', 0):.4f} |
| **Sharpe** | {avg_stats.get('sharpe', 0):.4f} |

## 3. Detailed Results
{walk_forward_df.to_markdown(index=True)}

---
*Powered by MLService*
"""
        report_path.write_text(report_content, encoding="utf-8")

        # 同步儲存 metadata.json
        metadata_path = report_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        print(f"\n✅ Experiment [{experiment_name}] results saved to: {report_dir}")
        return report_path

    def stage_model_bundle(self, source_dir: Path, target_dir: Path, files_to_copy: list[str]):
        """
        將模型成果從 source_dir 發布到 target_dir (通常是 production 目錄)。
        """
        import shutil
        print(f"📦 Staging model bundle from {source_dir} to {target_dir}...")
        target_dir.mkdir(parents=True, exist_ok=True)

        copied_files = []
        for f in files_to_copy:
            src_file = source_dir / f
            if src_file.exists():
                shutil.copy2(src_file, target_dir / f)
                copied_files.append(f)
                print(f"  - Copied {f}")
            else:
                print(f"  - ⚠️ Warning: {f} not found in {source_dir}")

        # 建立發布資訊
        info = {
            "staged_at": datetime.now(timezone.utc).isoformat(),
            "source_dir": str(source_dir.absolute()),
            "copied_files": copied_files,
        }
        info_path = target_dir / "staged_info.json"
        with open(info_path, "w", encoding="utf-8") as f_info:
            json.dump(info, f_info, indent=4)

        print(f"✅ Staged model info saved to {info_path}")
