import argparse
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure UTF-8 encoding for Windows consoles
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report
from sklearn.preprocessing import RobustScaler
from sklearn.utils.class_weight import compute_sample_weight

from com.willy.trade_bot.data_extractor.binance_extractor import BinanceExtractor
from com.willy.trade_bot.dto.crypto_extractor_dto import CryptoExtractorDto
from com.willy.trade_bot.enums.exchange import Exchange
from com.willy.trade_bot.enums.market_type import MarketType
from com.willy.trade_bot.enums.product import Product
from com.willy.trade_bot.enums.timeframe import Timeframe
from com.willy.trade_bot.service.ml_svc import MLService
from com.willy.trade_bot.service.tech_idx_svc import TECHNICAL_INDICATOR_COLUMNS, append_technical_indicators


class BinanceTechIdxModelTrainer:
    EXCLUDED_COLUMNS = ["start_time", "open", "high", "low", "close"]
    BACKGROUND_FEATURE_COLUMNS = [
        "sma_7_bias",
        "sma_25_bias",
        "sma_99_bias",
        "ema_7_bias",
        "ema_25_bias",
        "ema_99_bias",
        "ema_7_25_spread",
        "adx_14",
        "atr_scaled",
    ]
    DYNAMIC_FEATURE_SOURCE_COLUMNS = [
        "log_return",
        "rsi_14",
        "macd_hist",
        "kdj_j",
        "cci_14",
        "vol_pct_change",
        "bb_percent_b",
        "vwap_bias",
        "obv_diff",
    ]
    DYNAMIC_LAG_RANGE = range(1, 6)
    DEFAULT_LOOKAHEAD = 4
    DEFAULT_ATR_MULTIPLIER = 1.5
    DEFAULT_END_DT = None # Now dynamic
    DEFAULT_START_DT = None # Now dynamic
    DEFAULT_THRESHOLD_GRID = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70]

    def __init__(self, market_type: MarketType = MarketType.FUTURE):
        self.market_type = market_type
        self.extractor = BinanceExtractor()
        self.ml_svc = MLService()

    def fetch_ohlcv(self, start_dt: datetime = None, end_dt: datetime = None) -> dict[str, pd.DataFrame]:
        if end_dt is None:
            end_dt = datetime.now(timezone.utc)
        if start_dt is None:
            start_dt = end_dt - timedelta(days=730)

        target_timeframes = [
            Timeframe.MINUTE_15,
            Timeframe.HOUR_1,
            Timeframe.HOUR_4,
            Timeframe.DAY_1,
        ]

        data_by_timeframe: dict[str, pd.DataFrame] = {}
        for timeframe in target_timeframes:
            extractor_dto = CryptoExtractorDto(
                exchange=Exchange.BINANCE,
                product=Product.BTCUSDT,
                market_type=self.market_type,
                timeframe=timeframe,
                start_dt=start_dt,
                end_dt=end_dt,
            )
            df = self.extractor.extract(extractor_dto)
            if not df.empty:
                df = df[["start_time", "open", "high", "low", "close", "vol"]].copy()
            data_by_timeframe[timeframe.value] = df
        return data_by_timeframe

    def make_stationary(self, df: pd.DataFrame) -> pd.DataFrame:
        return self.ml_svc.make_log_returns(df)

    def model_feature_columns(self) -> list[str]:
        dynamic_lagged_columns = [
            f"{column}_lag_{lag}"
            for column in self.DYNAMIC_FEATURE_SOURCE_COLUMNS
            for lag in self.DYNAMIC_LAG_RANGE
        ]
        return [*self.BACKGROUND_FEATURE_COLUMNS, *dynamic_lagged_columns]

    def _validate_lag_feature_inputs(self, df: pd.DataFrame) -> None:
        allowed_volume_columns = {"vol", "volume"}
        allowed_columns = {
            *self.EXCLUDED_COLUMNS,
            "log_return",
            *TECHNICAL_INDICATOR_COLUMNS,
            *allowed_volume_columns,
        }
        required_columns = {
            *self.EXCLUDED_COLUMNS,
            "log_return",
            *TECHNICAL_INDICATOR_COLUMNS,
        }

        missing_columns = sorted(required_columns - set(df.columns))
        if missing_columns:
            raise ValueError(f"Lag feature pipeline missing expected columns: {missing_columns}")

        if not any(column in df.columns for column in allowed_volume_columns):
            raise ValueError("Lag feature pipeline requires a volume column: 'vol' or 'volume'.")

        unexpected_columns = sorted(set(df.columns) - allowed_columns)
        if unexpected_columns:
            raise ValueError(f"Lag feature pipeline received unexpected columns: {unexpected_columns}")

    def lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        self._validate_lag_feature_inputs(df)
        lagged_df = df.copy()

        volume_column = "vol" if "vol" in lagged_df.columns else "volume"
        close_price = pd.to_numeric(lagged_df["close"], errors="coerce")
        volume = pd.to_numeric(lagged_df[volume_column], errors="coerce")

        for period in (7, 25, 99):
            lagged_df[f"sma_{period}_bias"] = self.ml_svc.safe_divide(
                close_price,
                pd.to_numeric(lagged_df[f"sma_{period}"], errors="coerce"),
            ) - 1.0
            lagged_df[f"ema_{period}_bias"] = self.ml_svc.safe_divide(
                close_price,
                pd.to_numeric(lagged_df[f"ema_{period}"], errors="coerce"),
            ) - 1.0

        lagged_df["ema_7_25_spread"] = self.ml_svc.safe_divide(
            pd.to_numeric(lagged_df["ema_7"], errors="coerce"),
            pd.to_numeric(lagged_df["ema_25"], errors="coerce"),
        ) - 1.0
        lagged_df["atr_scaled"] = self.ml_svc.safe_divide(
            pd.to_numeric(lagged_df["atr_14"], errors="coerce"),
            close_price,
        )
        lagged_df["bb_percent_b"] = self.ml_svc.safe_divide(
            close_price - pd.to_numeric(lagged_df["bb_lower"], errors="coerce"),
            pd.to_numeric(lagged_df["bb_upper"], errors="coerce")
            - pd.to_numeric(lagged_df["bb_lower"], errors="coerce"),
        )
        lagged_df["vwap_bias"] = self.ml_svc.safe_divide(
            close_price,
            pd.to_numeric(lagged_df["vwap"], errors="coerce"),
        ) - 1.0
        lagged_df["obv_diff"] = pd.to_numeric(lagged_df["obv"], errors="coerce").diff()
        lagged_df["vol_pct_change"] = volume.pct_change().replace([np.inf, -np.inf], np.nan)

        for column in self.BACKGROUND_FEATURE_COLUMNS:
            lagged_df[column] = pd.to_numeric(lagged_df[column], errors="coerce").shift(1)

        for column in self.DYNAMIC_FEATURE_SOURCE_COLUMNS:
            feature_series = pd.to_numeric(lagged_df[column], errors="coerce")
            for lag in self.DYNAMIC_LAG_RANGE:
                lagged_df[f"{column}_lag_{lag}"] = feature_series.shift(lag)

        passthrough_columns = [
            column
            for column in [*self.EXCLUDED_COLUMNS, "vol", "volume", "atr_14"]
            if column in lagged_df
        ]
        output_columns = [*passthrough_columns, *self.model_feature_columns()]
        return lagged_df[output_columns]

    @staticmethod
    def _barrier_prices(entry_price: float, threshold: float) -> tuple[float, float]:
        return entry_price * np.exp(threshold), entry_price * np.exp(-threshold)

    def _resolve_label_and_returns(
            self,
            entry_price: float,
            threshold: float,
            future_highs: np.ndarray,
            future_lows: np.ndarray,
            exit_close: float,
    ) -> tuple[int, float, float]:
        upper_price, lower_price = self._barrier_prices(entry_price, threshold)
        target_action = 0
        long_return = np.log(exit_close / entry_price)
        short_return = np.log(entry_price / exit_close)

        for high_price, low_price in zip(future_highs, future_lows):
            hit_upper = high_price >= upper_price
            hit_lower = low_price <= lower_price

            if hit_upper and hit_lower:
                target_action = 0
                long_return = -threshold
                short_return = -threshold
                break
            if hit_upper:
                target_action = 1
                long_return = threshold
                short_return = -threshold
                break
            if hit_lower:
                target_action = -1
                long_return = -threshold
                short_return = threshold
                break

        return target_action, long_return, short_return

    def create_multi_class_target(self, df, lookahead=None, atr_multiplier=None):
        if lookahead is None:
            lookahead = self.DEFAULT_LOOKAHEAD
        if atr_multiplier is None:
            atr_multiplier = self.DEFAULT_ATR_MULTIPLIER

        df = df.copy().reset_index(drop=True)
        df["dynamic_threshold"] = (
            pd.to_numeric(df["atr_14"], errors="coerce") / pd.to_numeric(df["close"], errors="coerce")
        ) * atr_multiplier

        highs = pd.to_numeric(df["high"], errors="coerce").to_numpy()
        lows = pd.to_numeric(df["low"], errors="coerce").to_numpy()
        closes = pd.to_numeric(df["close"], errors="coerce").to_numpy()
        thresholds = pd.to_numeric(df["dynamic_threshold"], errors="coerce").to_numpy()

        target_actions = []
        long_returns = []
        short_returns = []
        hold_returns = []
        max_future_returns = []
        min_future_returns = []

        for idx in range(len(df)):
            if idx + lookahead >= len(df):
                target_actions.append(np.nan)
                long_returns.append(np.nan)
                short_returns.append(np.nan)
                hold_returns.append(np.nan)
                max_future_returns.append(np.nan)
                min_future_returns.append(np.nan)
                continue

            entry_price = closes[idx]
            threshold = thresholds[idx]
            future_slice = slice(idx + 1, idx + lookahead + 1)
            future_highs = highs[future_slice]
            future_lows = lows[future_slice]
            exit_close = closes[idx + lookahead]

            if (
                    np.isnan(entry_price)
                    or np.isnan(threshold)
                    or np.isnan(exit_close)
                    or np.isnan(future_highs).any()
                    or np.isnan(future_lows).any()
            ):
                target_actions.append(np.nan)
                long_returns.append(np.nan)
                short_returns.append(np.nan)
                hold_returns.append(np.nan)
                max_future_returns.append(np.nan)
                min_future_returns.append(np.nan)
                continue

            target_action, long_return, short_return = self._resolve_label_and_returns(
                entry_price=entry_price,
                threshold=threshold,
                future_highs=future_highs,
                future_lows=future_lows,
                exit_close=exit_close,
            )

            target_actions.append(target_action)
            long_returns.append(long_return)
            short_returns.append(short_return)
            hold_returns.append(0.0)
            max_future_returns.append(np.log(np.max(future_highs) / entry_price))
            min_future_returns.append(np.log(np.min(future_lows) / entry_price))

        df["max_future_return"] = max_future_returns
        df["min_future_return"] = min_future_returns
        df["target_action"] = target_actions
        df["long_event_return"] = long_returns
        df["short_event_return"] = short_returns
        df["hold_event_return"] = hold_returns

        df = df.dropna().reset_index(drop=True)

        exclude_cols = [
            "start_time",
            "open",
            "high",
            "low",
            "close",
            "vol",
            "max_future_return",
            "min_future_return",
            "target_action",
            "dynamic_threshold",
            "long_event_return",
            "short_event_return",
            "hold_event_return",
        ]
        feature_cols = [col for col in df.columns if col not in exclude_cols]

        X = df[feature_cols]
        Y = df["target_action"]
        return X, Y, df

    @staticmethod
    def _max_drawdown(equity_curve: pd.Series) -> float:
        running_max = equity_curve.cummax()
        drawdown = equity_curve - running_max
        return float(drawdown.min()) if not drawdown.empty else 0.0

    def run_backtest_stats(self, y_true, y_pred, df_test, fee=0.0004):
        if len(y_true) != len(y_pred) or len(y_pred) != len(df_test):
            return {"error": "Length mismatch"}

        required_columns = {"long_event_return", "short_event_return", "hold_event_return"}
        missing_columns = required_columns - set(df_test.columns)
        if missing_columns:
            return {"error": f"Missing event return columns: {sorted(missing_columns)}"}

        df = df_test.copy()
        df["pred"] = y_pred
        df["true"] = y_true
        df["trade_return"] = df["hold_event_return"]

        long_mask = df["pred"] == 1
        short_mask = df["pred"] == -1
        trade_mask = long_mask | short_mask

        df.loc[long_mask, "trade_return"] = df.loc[long_mask, "long_event_return"] - fee
        df.loc[short_mask, "trade_return"] = df.loc[short_mask, "short_event_return"] - fee

        trades = df.loc[trade_mask].copy()
        if trades.empty:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_pnl": 0.0,
                "sharpe": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
            }

        win_rate = float((trades["trade_return"] > 0).mean())
        total_pnl = float(trades["trade_return"].sum())
        avg_pnl = float(trades["trade_return"].mean())
        pnl_std = float(trades["trade_return"].std(ddof=0))
        sharpe = (avg_pnl / pnl_std * np.sqrt(365 * 96)) if pnl_std > 0 else 0.0

        gross_profit = float(trades.loc[trades["trade_return"] > 0, "trade_return"].sum())
        gross_loss = float(-trades.loc[trades["trade_return"] < 0, "trade_return"].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

        equity_curve = trades["trade_return"].cumsum()
        max_drawdown = self._max_drawdown(equity_curve)

        return {
            "total_trades": len(trades),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
            "sharpe": sharpe,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
        }

    def time_series_split_5way(
            self,
            X: pd.DataFrame,
            Y: pd.Series,
            train_ratio: float = 0.60,
            val_earlystop_ratio: float = 0.10,
            val_calibration_ratio: float = 0.10,
            val_threshold_ratio: float = 0.10,
            gap: int = 20,
    ) -> tuple[
        pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
        pd.Series, pd.Series, pd.Series, pd.Series, pd.Series,
    ]:
        if X is None or X.empty:
            raise ValueError("Feature dataframe X is empty; cannot perform time-series split.")
        if Y is None or Y.empty:
            raise ValueError("Target series Y is empty; cannot perform time-series split.")
        if len(X) != len(Y):
            raise ValueError(f"X/Y length mismatch: len(X)={len(X)}, len(Y)={len(Y)}")

        ratio_sum = train_ratio + val_earlystop_ratio + val_calibration_ratio + val_threshold_ratio
        if ratio_sum >= 1.0:
            raise ValueError(f"Split ratios must sum to < 1.0, got {ratio_sum:.4f}")

        n = len(X)
        n_train = int(n * train_ratio)
        n_val_early = int(n * val_earlystop_ratio)
        n_val_cal = int(n * val_calibration_ratio)
        n_val_th = int(n * val_threshold_ratio)

        train_start, train_end = 0, n_train
        val_early_start = train_end + gap
        val_early_end = val_early_start + n_val_early
        val_cal_start = val_early_end + gap
        val_cal_end = val_cal_start + n_val_cal
        val_th_start = val_cal_end + gap
        val_th_end = val_th_start + n_val_th
        test_start = val_th_end + gap
        test_end = n

        split_points = {
            "train": (train_start, train_end),
            "val_early": (val_early_start, val_early_end),
            "val_cal": (val_cal_start, val_cal_end),
            "val_th": (val_th_start, val_th_end),
            "test": (test_start, test_end),
        }
        for split_name, (start, end) in split_points.items():
            if start < 0 or end > n or end <= start:
                raise ValueError(f"Split '{split_name}' is invalid: start={start}, end={end}, total_rows={n}")

        return (
            X.iloc[train_start:train_end],
            X.iloc[val_early_start:val_early_end],
            X.iloc[val_cal_start:val_cal_end],
            X.iloc[val_th_start:val_th_end],
            X.iloc[test_start:test_end],
            Y.iloc[train_start:train_end],
            Y.iloc[val_early_start:val_early_end],
            Y.iloc[val_cal_start:val_cal_end],
            Y.iloc[val_th_start:val_th_end],
            Y.iloc[test_start:test_end],
        )

    def normalize_features_5way(
            self,
            X_train: pd.DataFrame,
            X_val_early: pd.DataFrame,
            X_val_cal: pd.DataFrame,
            X_val_th: pd.DataFrame,
            X_test: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, RobustScaler]:
        scaler = RobustScaler()
        return (
            pd.DataFrame(scaler.fit_transform(X_train), columns=X_train.columns, index=X_train.index),
            pd.DataFrame(scaler.transform(X_val_early), columns=X_val_early.columns, index=X_val_early.index),
            pd.DataFrame(scaler.transform(X_val_cal), columns=X_val_cal.columns, index=X_val_cal.index),
            pd.DataFrame(scaler.transform(X_val_th), columns=X_val_th.columns, index=X_val_th.index),
            pd.DataFrame(scaler.transform(X_test), columns=X_test.columns, index=X_test.index),
            scaler,
        )

    def merge_multi_timeframes(self, ohlcv_data: dict[str, pd.DataFrame], base_tf: str = "15m") -> pd.DataFrame:
        base_df = ohlcv_data[base_tf].copy().sort_values("start_time")
        for tf in [timeframe for timeframe in ohlcv_data.keys() if timeframe != base_tf]:
            higher_df = ohlcv_data[tf].copy().sort_values("start_time")
            higher_features = higher_df[["start_time", *self.model_feature_columns()]]
            base_df = pd.merge_asof(
                base_df,
                higher_features,
                on="start_time",
                direction="backward",
                suffixes=("", f"_{tf}"),
            )
        return base_df.dropna().reset_index(drop=True)

    def recommended_gap(self, lookahead: int) -> int:
        return max(lookahead, max(self.DYNAMIC_LAG_RANGE))

    def train_xgboost_model_v4(self, X_train, Y_train, X_val_earlystop, Y_val_earlystop):
        y_train_mapped = Y_train.map({-1: 0, 0: 1, 1: 2})
        y_val_early_mapped = Y_val_earlystop.map({-1: 0, 0: 1, 1: 2})
        sample_weights = compute_sample_weight(class_weight="balanced", y=y_train_mapped)

        model = xgb.XGBClassifier(
            n_estimators=1500,
            early_stopping_rounds=50,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="multi:softprob",
            num_class=3,
            random_state=42,
            n_jobs=-1,
            eval_metric="mlogloss",
        )
        model.fit(
            X_train,
            y_train_mapped,
            sample_weight=sample_weights,
            eval_set=[(X_val_earlystop, y_val_early_mapped)],
            verbose=100,
        )
        return model

    def calibrate_model(self, fitted_model, X_val_calibration, Y_val_calibration):
        y_val_cal_mapped = Y_val_calibration.map({-1: 0, 0: 1, 1: 2})
        try:
            from sklearn.frozen import FrozenEstimator

            calibrated_model = CalibratedClassifierCV(
                FrozenEstimator(fitted_model),
                method="isotonic",
                cv=None,
            )
        except ImportError:
            calibrated_model = CalibratedClassifierCV(
                fitted_model,
                method="isotonic",
                cv="prefit",
            )
        calibrated_model.fit(X_val_calibration, y_val_cal_mapped)
        return calibrated_model

    @staticmethod
    def _apply_thresholds(probabilities: np.ndarray, short_threshold: float, long_threshold: float) -> np.ndarray:
        predictions = np.zeros(len(probabilities), dtype=int)
        short_mask = probabilities[:, 0] > short_threshold
        long_mask = probabilities[:, 2] > long_threshold
        predictions[short_mask] = -1
        predictions[long_mask] = 1

        conflict_indices = np.where(short_mask & long_mask)[0]
        for idx in conflict_indices:
            predictions[idx] = -1 if probabilities[idx, 0] >= probabilities[idx, 2] else 1
        return predictions

    def find_best_thresholds_on_val(self, calibrated_model, X_val_threshold, Y_val_threshold, df_val_threshold):
        probabilities = calibrated_model.predict_proba(X_val_threshold)
        best_results = {"short": 0.50, "long": 0.50}
        best_score = None

        for short_threshold in self.DEFAULT_THRESHOLD_GRID:
            for long_threshold in self.DEFAULT_THRESHOLD_GRID:
                y_pred = self._apply_thresholds(probabilities, short_threshold, long_threshold)
                stats = self.run_backtest_stats(Y_val_threshold.values, y_pred, df_val_threshold)
                if "error" in stats or stats["total_trades"] < 5:
                    continue
                score = (
                    stats["total_pnl"],
                    stats["sharpe"],
                    stats["profit_factor"],
                    stats["total_trades"],
                )
                print(
                    f"Short TH: {short_threshold:.2f} | Long TH: {long_threshold:.2f} | "
                    f"Trades: {stats['total_trades']} | PnL: {stats['total_pnl']:.4f} | "
                    f"Sharpe: {stats['sharpe']:.4f}"
                )
                if best_score is None or score > best_score:
                    best_score = score
                    best_results = {"short": short_threshold, "long": long_threshold}

        print(
            f"Selected thresholds -> Short: {best_results['short']:.2f} | "
            f"Long: {best_results['long']:.2f}"
        )
        return best_results

    def final_blind_test(self, calibrated_model, X_test, Y_test, df_test, short_threshold, long_threshold):
        y_test_mapped = Y_test.map({-1: 0, 0: 1, 1: 2})
        probabilities = calibrated_model.predict_proba(X_test)
        final_y_pred = self._apply_thresholds(probabilities, short_threshold, long_threshold)
        custom_predictions = np.where(final_y_pred == -1, 0, np.where(final_y_pred == 1, 2, 1))

        target_names = ["Short (-1)", "Hold (0)", "Long (1)"]
        print(classification_report(y_test_mapped, custom_predictions, target_names=target_names, digits=4))

        stats = self.run_backtest_stats(Y_test.values, final_y_pred, df_test)
        print("Blind test trading stats:")
        for key, value in stats.items():
            if isinstance(value, (float, int)) and np.isfinite(value):
                print(f"  {key:15}: {value:.4f}")
            else:
                print(f"  {key:15}: {value}")
        return final_y_pred, probabilities, stats

    def walk_forward_train(self, mtf_df, window_size_ratio=0.8, step_size_ratio=0.1):
        n = len(mtf_df)
        window_size = int(n * window_size_ratio)
        step_size = int(n * step_size_ratio)

        results = []
        last_model_bundle = None
        start = 0
        while start + window_size + step_size <= n:
            test_end = start + window_size + step_size
            window_df = mtf_df.iloc[start:test_end].copy()
            print(f"Window: {window_df['start_time'].iloc[0]} -> {window_df['start_time'].iloc[-1]}")
            res = self.train_single_window(window_df)
            if res is not None:
                stats, model_bundle = res
                results.append(stats)
                last_model_bundle = model_bundle
            start += step_size

        if not results:
            return pd.DataFrame(), None

        res_df = pd.DataFrame(results)
        print("Walk-forward mean stats:")
        print(res_df.mean(numeric_only=True))
        return res_df, last_model_bundle

    def train_single_window(self, mtf_df):
        lookahead = self.DEFAULT_LOOKAHEAD
        X, Y, cleaned_df = self.create_multi_class_target(
            mtf_df,
            lookahead=lookahead,
            atr_multiplier=self.DEFAULT_ATR_MULTIPLIER,
        )

        try:
            (
                X_train, X_val_early, X_val_cal, X_val_th, X_test,
                Y_train, Y_val_early, Y_val_cal, Y_val_th, Y_test,
            ) = self.ml_svc.time_series_split_5way(X, Y, gap=self.recommended_gap(lookahead))

            df_val_th = cleaned_df.loc[X_val_th.index].reset_index(drop=True)
            df_test = cleaned_df.loc[X_test.index].reset_index(drop=True)

            (
                X_train_scaled, X_val_early_scaled, X_val_cal_scaled,
                X_val_th_scaled, X_test_scaled, scaler,
            ) = self.ml_svc.normalize_features_5way(X_train, X_val_early, X_val_cal, X_val_th, X_test)

            base_model = self.train_xgboost_model_v4(X_train_scaled, Y_train, X_val_early_scaled, Y_val_early)
            calibrated_model = self.calibrate_model(base_model, X_val_cal_scaled, Y_val_cal)
            best_thresholds = self.find_best_thresholds_on_val(
                calibrated_model,
                X_val_th_scaled,
                Y_val_th,
                df_val_th,
            )
            _, _, stats = self.final_blind_test(
                calibrated_model,
                X_test_scaled,
                Y_test,
                df_test,
                best_thresholds["short"],
                best_thresholds["long"],
            )
            stats["best_short_threshold"] = best_thresholds["short"]
            stats["best_long_threshold"] = best_thresholds["long"]
            stats["best_iteration"] = getattr(base_model, "best_iteration", None)
            stats["scaler_features"] = len(scaler.feature_names_in_) if hasattr(scaler, "feature_names_in_") else 0
            return stats, (calibrated_model, scaler, best_thresholds)
        except Exception as exc:
            print(f"Window training failed: {exc}")
            return None

    def save_model_bundle(self, bundle, output_dir: Path):
        model, scaler, thresholds = bundle
        output_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, output_dir / "model.joblib")
        joblib.dump(scaler, output_dir / "scaler.joblib")
        with open(output_dir / "thresholds.json", "w") as f:
            json.dump(thresholds, f, indent=4)
        print(f"Model bundle saved to {output_dir}")

    def stage_model_bundle(self, source_dir: Path, target_dir: Path):
        """
        Stage a model bundle from a source directory to a production directory.
        """
        files_to_copy = ["model.joblib", "scaler.joblib", "thresholds.json"]
        self.ml_svc.stage_model_bundle(source_dir, target_dir, files_to_copy)


def train(experiment_name: str = "default_experiment", start_dt: datetime = None, end_dt: datetime = None, output_dir: Path = None):
    trainer = BinanceTechIdxModelTrainer()
    if end_dt is None:
        end_dt = trainer.DEFAULT_END_DT
    if start_dt is None:
        start_dt = trainer.DEFAULT_START_DT

    ohlcv_data = trainer.fetch_ohlcv(start_dt=start_dt, end_dt=end_dt)
    base_tf = Timeframe.MINUTE_15.value

    for timeframe, df in ohlcv_data.items():
        if df.empty:
            continue
        df = trainer.make_stationary(df)
        df = append_technical_indicators(df)
        df = trainer.lag_features(df)
        df = df.dropna(subset=trainer.model_feature_columns()).reset_index(drop=True)
        ohlcv_data[timeframe] = df

    print(f"Running Experiment: {experiment_name}")
    print("Running multi-timeframe feature join...")
    mtf_df = trainer.merge_multi_timeframes(ohlcv_data, base_tf=base_tf)
    walk_forward_df, last_model_bundle = trainer.walk_forward_train(mtf_df)

    metadata = {
        "experiment_name": experiment_name,
        "start_dt": start_dt.isoformat(),
        "end_dt": end_dt.isoformat(),
        "lookahead": trainer.DEFAULT_LOOKAHEAD,
        "atr_multiplier": trainer.DEFAULT_ATR_MULTIPLIER,
        "recommended_gap": trainer.recommended_gap(trainer.DEFAULT_LOOKAHEAD),
        "base_tf": base_tf,
        "rows_after_mtf_join": int(len(mtf_df)),
        "walk_forward_windows": int(len(walk_forward_df)),
    }

    if not walk_forward_df.empty:
        # 產出 Markdown 實驗報告 (透過 MLService)
        trainer.ml_svc.export_experiment_report(
            experiment_name, walk_forward_df, metadata, trainer.model_feature_columns()
        )

        if output_dir and last_model_bundle:
            trainer.save_model_bundle(last_model_bundle, output_dir)

    return walk_forward_df


def stage(source_dir: Path = None, target_dir: Path = None):
    trainer = BinanceTechIdxModelTrainer()
    if target_dir is None:
        target_dir = Path(__file__).parent / "production"

    if source_dir is None:
        generated_dir = Path(__file__).parent / "generated"
        if not generated_dir.exists():
            print(f"No generated directory found at {generated_dir}")
            return

        # Find latest model directory in generated/
        model_dirs = sorted([d for d in generated_dir.iterdir() if d.is_dir() and d.name.startswith("model_")])
        if not model_dirs:
            print(f"No model directories found in {generated_dir}")
            return
        source_dir = model_dirs[-1]

    trainer.stage_model_bundle(source_dir, target_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Binance Technical Indicator Model Trainer")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Train command
    train_parser = subparsers.add_parser("train", help="Train a new model")
    train_parser.add_argument("--name", type=str, default="baseline_v1", help="Experiment name")
    train_parser.add_argument("--output", type=str, help="Output directory for the model")

    # Stage command
    stage_parser = subparsers.add_parser("stage", help="Stage a model to production")
    stage_parser.add_argument("--source", type=str, help="Source model directory")
    stage_parser.add_argument("--target", type=str, help="Target production directory")

    args = parser.parse_args()

    if args.command == "train":
        output_path = Path(args.output) if args.output else Path(__file__).parent / "generated" / f"model_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        train(experiment_name=args.name, output_dir=output_path)
    elif args.command == "stage":
        source_path = Path(args.source) if args.source else None
        target_path = Path(args.target) if args.target else None
        stage(source_dir=source_path, target_dir=target_path)
    else:
        parser.print_help()
