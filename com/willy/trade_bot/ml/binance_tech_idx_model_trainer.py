from datetime import datetime, timedelta, timezone

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report, accuracy_score
from sklearn.preprocessing import RobustScaler
from sklearn.utils.class_weight import compute_sample_weight

from com.willy.trade_bot.data_extractor.binance_extractor import BinanceExtractor
from com.willy.trade_bot.dto.crypto_extractor_dto import CryptoExtractorDto
from com.willy.trade_bot.enums.exchange import Exchange
from com.willy.trade_bot.enums.market_type import MarketType
from com.willy.trade_bot.enums.product import Product
from com.willy.trade_bot.enums.timeframe import Timeframe
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

    def __init__(self, market_type: MarketType = MarketType.FUTURE):
        self.market_type = market_type
        self.extractor = BinanceExtractor()

    def fetch_ohlcv(self) -> dict[str, pd.DataFrame]:
        end_dt = datetime.now(timezone.utc)
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
        if df is None or df.empty:
            return df

        stationary_df = df.copy()
        stationary_df["log_return"] = np.log(stationary_df["close"] / stationary_df["close"].shift(1))
        return stationary_df

    @staticmethod
    def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
        denominator = denominator.replace(0, np.nan)
        return (numerator / denominator).replace([np.inf, -np.inf], np.nan)

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
            raise ValueError(
                "Lag feature pipeline received unexpected columns that are not in the handling list: "
                f"{unexpected_columns}"
            )

    def lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        self._validate_lag_feature_inputs(df)
        lagged_df = df.copy()

        volume_column = "vol" if "vol" in lagged_df.columns else "volume"
        close_price = pd.to_numeric(lagged_df["close"], errors="coerce")
        volume = pd.to_numeric(lagged_df[volume_column], errors="coerce")

        for period in (7, 25, 99):
            lagged_df[f"sma_{period}_bias"] = self._safe_divide(
                close_price,
                pd.to_numeric(lagged_df[f"sma_{period}"], errors="coerce"),
            ) - 1.0
            lagged_df[f"ema_{period}_bias"] = self._safe_divide(
                close_price,
                pd.to_numeric(lagged_df[f"ema_{period}"], errors="coerce"),
            ) - 1.0

        lagged_df["ema_7_25_spread"] = self._safe_divide(
            pd.to_numeric(lagged_df["ema_7"], errors="coerce"),
            pd.to_numeric(lagged_df["ema_25"], errors="coerce"),
        ) - 1.0
        lagged_df["atr_scaled"] = self._safe_divide(
            pd.to_numeric(lagged_df["atr_14"], errors="coerce"),
            close_price,
        )
        lagged_df["bb_percent_b"] = self._safe_divide(
            close_price - pd.to_numeric(lagged_df["bb_lower"], errors="coerce"),
            pd.to_numeric(lagged_df["bb_upper"], errors="coerce")
            - pd.to_numeric(lagged_df["bb_lower"], errors="coerce"),
        )
        lagged_df["vwap_bias"] = self._safe_divide(
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

        passthrough_columns = [column for column in [*self.EXCLUDED_COLUMNS, "vol", "volume"] if column in lagged_df]
        output_columns = [*passthrough_columns, *self.model_feature_columns()]
        return lagged_df[output_columns]

    def create_multi_class_target(self, df, threshold=0.003, lookahead=4):
        """
        產生未來 N 根 K 線的三元分類標籤 (防雙向觸發版)：
        1 : 未來 N 根 K 線內，最高價觸及目標利潤 (+threshold)，且最低價未觸及停損 (-threshold)
        -1: 未來 N 根 K 線內，最低價觸及目標利潤 (-threshold)，且最高價未觸及停損 (+threshold)
        0 : 盤整，或者「同時觸發上下邊界 (震盪過大，無法確定先後順序)」皆視為觀望
        """
        df = df.copy()

        future_high = df['high'].rolling(window=lookahead).max().shift(-lookahead)
        future_low = df['low'].rolling(window=lookahead).min().shift(-lookahead)

        df['max_future_return'] = np.log(future_high / df['close'])
        df['min_future_return'] = np.log(future_low / df['close'])

        df['target_action'] = 0
        cond_long = (df['max_future_return'] > threshold) & (df['min_future_return'] >= -threshold)
        cond_short = (df['min_future_return'] < -threshold) & (df['max_future_return'] <= threshold)

        df.loc[cond_long, 'target_action'] = 1
        df.loc[cond_short, 'target_action'] = -1

        df = df.dropna().reset_index(drop=True)

        exclude_cols = [
            'start_time', 'open', 'high', 'low', 'close', 'vol',
            'max_future_return', 'min_future_return', 'target_action'
        ]
        feature_cols = [col for col in df.columns if col not in exclude_cols]

        X = df[feature_cols]
        Y = df['target_action']
        return X, Y, df

    def time_series_split(
            self,
            X: pd.DataFrame,
            Y: pd.Series,
            split_ratio: float = 0.8,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        if X is None or X.empty:
            raise ValueError("Feature dataframe X is empty; cannot perform time-series split.")
        if Y is None or Y.empty:
            raise ValueError("Target series Y is empty; cannot perform time-series split.")
        if len(X) != len(Y):
            raise ValueError(f"X/Y length mismatch: len(X)={len(X)}, len(Y)={len(Y)}")
        if not 0 < split_ratio < 1:
            raise ValueError(f"split_ratio must be between 0 and 1, got {split_ratio}")

        split_idx = int(len(X) * split_ratio)
        if split_idx <= 0 or split_idx >= len(X):
            raise ValueError(
                f"Invalid split index {split_idx} for dataset length {len(X)} and ratio {split_ratio}"
            )

        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        Y_train, Y_test = Y.iloc[:split_idx], Y.iloc[split_idx:]

        print(f"訓練集大小: {len(X_train)}, 測試集大小: {len(X_test)}")
        return X_train, X_test, Y_train, Y_test

    def normalize_features(
            self,
            X_train: pd.DataFrame,
            X_test: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame, RobustScaler]:
        if X_train is None or X_train.empty:
            raise ValueError("X_train is empty; cannot fit RobustScaler.")
        if X_test is None or X_test.empty:
            raise ValueError("X_test is empty; cannot transform with RobustScaler.")

        scaler = RobustScaler()
        X_train_scaled = pd.DataFrame(
            scaler.fit_transform(X_train),
            columns=X_train.columns,
            index=X_train.index,
        )
        X_test_scaled = pd.DataFrame(
            scaler.transform(X_test),
            columns=X_test.columns,
            index=X_test.index,
        )
        return X_train_scaled, X_test_scaled, scaler

    def merge_multi_timeframes(self, ohlcv_data: dict[str, pd.DataFrame], base_tf: str = "15m") -> pd.DataFrame:
        """
        將多個時區的資料，以 base_tf 為主表進行向後對齊合併 (避免前視偏誤)。
        """
        base_df = ohlcv_data[base_tf].copy()
        base_df = base_df.sort_values("start_time")

        higher_tfs = [tf for tf in ohlcv_data.keys() if tf != base_tf]
        for tf in higher_tfs:
            higher_df = ohlcv_data[tf].copy().sort_values("start_time")
            feature_columns = self.model_feature_columns()
            higher_features = higher_df[["start_time", *feature_columns]]

            base_df = pd.merge_asof(
                base_df,
                higher_features,
                on="start_time",
                direction="backward",
                suffixes=("", f"_{tf}")
            )

        base_df = base_df.dropna().reset_index(drop=True)
        return base_df

    def train_xgboost_model(self, X_train, Y_train, X_test, Y_test):
        print("\n" + "=" * 40)
        print("🧠 開始訓練 XGBoost 模型...")
        print("=" * 40)

        Y_train_mapped = Y_train.map({-1: 0, 0: 1, 1: 2})
        Y_test_mapped = Y_test.map({-1: 0, 0: 1, 1: 2})

        model = xgb.XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective='multi:softmax',
            num_class=3,
            random_state=42,
            n_jobs=-1
        )

        model.fit(
            X_train,
            Y_train_mapped,
            eval_set=[(X_train, Y_train_mapped), (X_test, Y_test_mapped)],
            verbose=50
        )

        predictions = model.predict(X_test)

        print("\n📊 模型測試集評估報告:")
        print(f"整體準確率 (Accuracy): {accuracy_score(Y_test_mapped, predictions):.4f}")

        target_names = ['Short (-1)', 'Hold (0)', 'Long (1)']
        print("\n" + classification_report(Y_test_mapped, predictions, target_names=target_names))

        print("\n繪製特徵重要性圖表...")
        feature_importances = pd.Series(model.feature_importances_, index=X_train.columns)
        top_features = feature_importances.sort_values(ascending=True).tail(20)

        plt.figure(figsize=(10, 8))
        top_features.plot(kind='barh', color='teal')
        plt.title('Top 20 Most Important Features (XGBoost)')
        plt.xlabel('Importance Score')
        plt.tight_layout()
        plt.show()

        return model

    def train_xgboost_model_v2(self, X_train, Y_train, X_test, Y_test, threshold):
        print("\n" + "=" * 40)
        print("🚀 啟動進化版 XGBoost 模型 (含權重平衡 & Early Stopping)")
        print("=" * 40)

        Y_train_mapped = Y_train.map({-1: 0, 0: 1, 1: 2})
        Y_test_mapped = Y_test.map({-1: 0, 0: 1, 1: 2})
        sample_weights = compute_sample_weight(class_weight='balanced', y=Y_train_mapped)

        print("已自動計算並套用類別權重 (Balanced)")

        model = xgb.XGBClassifier(
            n_estimators=500,
            early_stopping_rounds=20,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective='multi:softmax',
            num_class=3,
            random_state=42,
            n_jobs=-1,
            eval_metric='mlogloss'
        )

        model.fit(
            X_train,
            Y_train_mapped,
            sample_weight=sample_weights,
            eval_set=[(X_train, Y_train_mapped), (X_test, Y_test_mapped)],
            verbose=50
        )

        best_iteration = model.best_iteration
        print(f"\n✅ Early Stopping 觸發！最佳模型停在第 {best_iteration} 棵樹")

        predictions = model.predict(X_test)
        target_names = ['Short (-1)', 'Hold (0)', 'Long (1)']
        print("\n📊 進化版模型測試集評估報告:")
        print(classification_report(Y_test_mapped, predictions, target_names=target_names))

        feature_importances = pd.Series(model.feature_importances_, index=X_train.columns)
        top_features = feature_importances.sort_values(ascending=True).tail(20)

        plt.figure(figsize=(10, 8))
        top_features.plot(kind='barh', color='darkorange')
        plt.title(f'Top 20 Important Features (Best Iteration: {best_iteration})')
        plt.xlabel('Importance Score')
        plt.tight_layout()
        plt.savefig(f'feature_importance_latest_{threshold}.png')
        plt.close()

        return model

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
        pd.Series, pd.Series, pd.Series, pd.Series, pd.Series
    ]:
        """
        嚴格時序切分:
        Train -> gap -> Val(Early Stop) -> gap -> Val(Calibration)
              -> gap -> Val(Threshold) -> gap -> Test
        """
        if X is None or X.empty:
            raise ValueError("Feature dataframe X is empty; cannot perform time-series split.")
        if Y is None or Y.empty:
            raise ValueError("Target series Y is empty; cannot perform time-series split.")
        if len(X) != len(Y):
            raise ValueError(f"X/Y length mismatch: len(X)={len(X)}, len(Y)={len(Y)}")

        ratio_sum = train_ratio + val_earlystop_ratio + val_calibration_ratio + val_threshold_ratio
        if ratio_sum >= 1.0:
            raise ValueError(
                "train_ratio + val_earlystop_ratio + val_calibration_ratio + "
                f"val_threshold_ratio must be < 1.0, got {ratio_sum:.4f}"
            )

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
            "val_earlystop": (val_early_start, val_early_end),
            "val_calibration": (val_cal_start, val_cal_end),
            "val_threshold": (val_th_start, val_th_end),
            "test": (test_start, test_end),
        }

        for split_name, (start, end) in split_points.items():
            if start < 0 or end > n or end <= start:
                raise ValueError(
                    f"Split '{split_name}' is empty or invalid: start={start}, end={end}, total_rows={n}"
                )

        X_train, Y_train = X.iloc[train_start:train_end], Y.iloc[train_start:train_end]
        X_val_early, Y_val_early = X.iloc[val_early_start:val_early_end], Y.iloc[val_early_start:val_early_end]
        X_val_cal, Y_val_cal = X.iloc[val_cal_start:val_cal_end], Y.iloc[val_cal_start:val_cal_end]
        X_val_th, Y_val_th = X.iloc[val_th_start:val_th_end], Y.iloc[val_th_start:val_th_end]
        X_test, Y_test = X.iloc[test_start:test_end], Y.iloc[test_start:test_end]

        print(
            f"嚴格 5 段切分 (每段間隔 {gap} 根 K 線) -> "
            f"Train: {len(X_train)} | "
            f"ValEarly: {len(X_val_early)} | "
            f"ValCal: {len(X_val_cal)} | "
            f"ValTh: {len(X_val_th)} | "
            f"Test: {len(X_test)}"
        )

        return (
            X_train, X_val_early, X_val_cal, X_val_th, X_test,
            Y_train, Y_val_early, Y_val_cal, Y_val_th, Y_test,
        )

    def normalize_features_5way(
            self,
            X_train: pd.DataFrame,
            X_val_early: pd.DataFrame,
            X_val_cal: pd.DataFrame,
            X_val_th: pd.DataFrame,
            X_test: pd.DataFrame,
    ) -> tuple[
        pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, RobustScaler
    ]:
        if X_train is None or X_train.empty:
            raise ValueError("X_train is empty; cannot fit RobustScaler.")

        scaler = RobustScaler()

        X_train_scaled = pd.DataFrame(
            scaler.fit_transform(X_train), columns=X_train.columns, index=X_train.index
        )
        X_val_early_scaled = pd.DataFrame(
            scaler.transform(X_val_early), columns=X_val_early.columns, index=X_val_early.index
        )
        X_val_cal_scaled = pd.DataFrame(
            scaler.transform(X_val_cal), columns=X_val_cal.columns, index=X_val_cal.index
        )
        X_val_th_scaled = pd.DataFrame(
            scaler.transform(X_val_th), columns=X_val_th.columns, index=X_val_th.index
        )
        X_test_scaled = pd.DataFrame(
            scaler.transform(X_test), columns=X_test.columns, index=X_test.index
        )

        return (
            X_train_scaled,
            X_val_early_scaled,
            X_val_cal_scaled,
            X_val_th_scaled,
            X_test_scaled,
            scaler,
        )

    def train_xgboost_model_v4(self, X_train, Y_train, X_val_earlystop, Y_val_earlystop):
        """
        只用 Val(Early Stop) 做 early stopping。
        不在這裡做 calibration，避免同一份 validation 被重複使用。
        """
        print("\n" + "=" * 40)
        print("🚀 啟動 V4 XGBoost 模型 (拆分 EarlyStop / Calibration / Threshold)")
        print("=" * 40)

        Y_train_mapped = Y_train.map({-1: 0, 0: 1, 1: 2})
        Y_val_early_mapped = Y_val_earlystop.map({-1: 0, 0: 1, 1: 2})
        sample_weights = compute_sample_weight(class_weight='balanced', y=Y_train_mapped)

        model = xgb.XGBClassifier(
            n_estimators=1500,
            early_stopping_rounds=50,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective='multi:softprob',
            num_class=3,
            random_state=42,
            n_jobs=-1,
            eval_metric='mlogloss'
        )

        model.fit(
            X_train,
            Y_train_mapped,
            sample_weight=sample_weights,
            eval_set=[(X_val_earlystop, Y_val_early_mapped)],
            verbose=100
        )

        print(f"\n✅ Early Stopping 完成！最佳模型停在第 {model.best_iteration} 棵樹")
        return model

    def calibrate_model(self, fitted_model, X_val_calibration, Y_val_calibration):
        """
        只用獨立的 Val(Calibration) 做 isotonic calibration。
        """
        print("\n🔧 開始進行獨立 Calibration...")

        Y_val_cal_mapped = Y_val_calibration.map({-1: 0, 0: 1, 1: 2})
        calibrated_model = CalibratedClassifierCV(
            fitted_model,
            method='isotonic',
            cv='prefit'
        )
        calibrated_model.fit(X_val_calibration, Y_val_cal_mapped)

        print("✅ Calibration 完成！")
        return calibrated_model

    def _search_one_sided_threshold(
            self,
            probabilities: np.ndarray,
            y_true_mapped: np.ndarray,
            target_class: int,
            side_name: str,
            candidate_thresholds=None,
            min_signals: int = 10,
    ) -> tuple[float, float, int]:
        if candidate_thresholds is None:
            candidate_thresholds = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70]

        best_th = 0.50
        best_precision = -1.0
        best_count = 0

        for th in candidate_thresholds:
            selected = probabilities > th
            count = int(np.sum(selected))

            if count < min_signals:
                print(f"{side_name} 門檻 {th * 100:.0f}% -> 跳過，觸發次數不足 ({count})")
                continue

            precision = float(np.mean(y_true_mapped[selected] == target_class))
            print(
                f"{side_name} 門檻 {th * 100:.0f}% -> "
                f"Precision: {precision:.4f} | 觸發次數: {count}"
            )

            if (precision > best_precision) or (
                    np.isclose(precision, best_precision) and count > best_count
            ):
                best_precision = precision
                best_th = th
                best_count = count

        if best_precision < 0:
            print(f"⚠️ {side_name} 沒有任何門檻滿足 min_signals={min_signals}，改用預設 50%")
            return 0.50, 0.0, 0

        return best_th, best_precision, best_count

    def find_best_thresholds_on_val(self, calibrated_model, X_val_threshold, Y_val_threshold):
        """
        在獨立的 Val(Threshold) 上分別找 Short / Long 的最佳門檻。
        """
        print("\n🔍 正在 Val(Threshold) 上尋找 Short / Long 最佳門檻...")

        y_val_mapped = Y_val_threshold.map({-1: 0, 0: 1, 1: 2}).values
        probabilities = calibrated_model.predict_proba(X_val_threshold)

        short_th, short_precision, short_count = self._search_one_sided_threshold(
            probabilities=probabilities[:, 0],
            y_true_mapped=y_val_mapped,
            target_class=0,
            side_name="Short",
        )

        long_th, long_precision, long_count = self._search_one_sided_threshold(
            probabilities=probabilities[:, 2],
            y_true_mapped=y_val_mapped,
            target_class=2,
            side_name="Long",
        )

        print(
            f"\n🏆 選定最佳門檻 -> "
            f"Short: {short_th * 100:.1f}% (Precision={short_precision:.4f}, N={short_count}) | "
            f"Long : {long_th * 100:.1f}% (Precision={long_precision:.4f}, N={long_count})"
        )

        return {
            "short": short_th,
            "long": long_th,
            "short_precision": short_precision,
            "long_precision": long_precision,
            "short_count": short_count,
            "long_count": long_count,
        }

    def final_blind_test(self, calibrated_model, X_test, Y_test, short_threshold, long_threshold):
        """
        使用獨立選出的 short / long 門檻，對 Test Set 做唯一一次盲測。
        """
        print("\n" + "=" * 50)
        print(
            f"🔥 最終絕對盲測 (Test Set) - "
            f"Short 門檻: {short_threshold * 100:.1f}% | "
            f"Long 門檻: {long_threshold * 100:.1f}%"
        )
        print("=" * 50)

        Y_test_mapped = Y_test.map({-1: 0, 0: 1, 1: 2})
        probabilities = calibrated_model.predict_proba(X_test)

        custom_predictions = np.full(len(probabilities), 1, dtype=int)
        strong_short_idx = probabilities[:, 0] > short_threshold
        strong_long_idx = probabilities[:, 2] > long_threshold

        custom_predictions[strong_short_idx] = 0
        custom_predictions[strong_long_idx] = 2

        conflict_idx = strong_short_idx & strong_long_idx
        custom_predictions[conflict_idx] = 1

        target_names = ['Short (-1)', 'Hold (0)', 'Long (1)']
        print(classification_report(Y_test_mapped, custom_predictions, target_names=target_names, digits=4))

        return custom_predictions, probabilities

    def evaluate_with_confidence(self, model, X_test, Y_test, short_threshold=0.50, long_threshold=0.50):
        """
        使用 predict_proba 取得機率，並以獨立的 short / long 門檻過濾交易訊號。
        """
        print("\n" + "=" * 50)
        print(
            f"🎯 啟用機率決策模式 "
            f"(Short 門檻: {short_threshold * 100:.1f}% | Long 門檻: {long_threshold * 100:.1f}%)"
        )
        print("=" * 50)

        Y_test_mapped = Y_test.map({-1: 0, 0: 1, 1: 2})
        probabilities = model.predict_proba(X_test)
        custom_predictions = np.full(len(probabilities), 1, dtype=int)

        p_short = probabilities[:, 0]
        p_long = probabilities[:, 2]

        strong_short_idx = p_short > short_threshold
        strong_long_idx = p_long > long_threshold

        custom_predictions[strong_short_idx] = 0
        custom_predictions[strong_long_idx] = 2

        conflict_idx = strong_short_idx & strong_long_idx
        custom_predictions[conflict_idx] = 1

        target_names = ['Short (-1)', 'Hold (0)', 'Long (1)']
        print(classification_report(Y_test_mapped, custom_predictions, target_names=target_names, digits=4))

        original_predictions = model.predict(X_test)
        original_trades = np.sum((original_predictions == 0) | (original_predictions == 2))
        new_trades = np.sum((custom_predictions == 0) | (custom_predictions == 2))

        print(f"💡 交易次數變化: 原本 {original_trades} 次 -> 過濾後 {new_trades} 次")
        if original_trades > 0:
            print(f"💡 訊號過濾率: {((original_trades - new_trades) / original_trades) * 100:.2f}% 的低信心訊號被捨棄")

        return custom_predictions, probabilities


def train():
    trainer = BinanceTechIdxModelTrainer()
    ohlcv_data = trainer.fetch_ohlcv()
    base_tf = Timeframe.MINUTE_15.value

    for timeframe, df in ohlcv_data.items():
        df = trainer.make_stationary(df)
        df = append_technical_indicators(df)
        if df is None or df.empty:
            ohlcv_data[timeframe] = df
            print(f"{timeframe}: rows=0")
            continue

        df = trainer.lag_features(df)
        df = df.dropna(subset=trainer.model_feature_columns()).reset_index(drop=True)
        ohlcv_data[timeframe] = df

    print("\n--- 執行多時區特徵整合 (MTF Join) ---")
    mtf_df = trainer.merge_multi_timeframes(ohlcv_data, base_tf=base_tf)
    print(f"整合後大表欄位數: {len(mtf_df.columns)}")
    print(f"整合後大表資料筆數: {len(mtf_df)}")

    test_thresholds = [0.005]
    lookahead_bars = 4

    for th in test_thresholds:
        print(f"\n\n{'=' * 50}")
        print(f"🔬 正在測試 目標利潤: {th * 100}%, 觀察期: {lookahead_bars} 根 K 線")
        print(f"{'=' * 50}")

        threshold_map = {
            Timeframe.MINUTE_15.value: th,
            Timeframe.HOUR_1.value: 0.005,
            Timeframe.HOUR_4.value: 0.01,
            Timeframe.DAY_1.value: 0.02,
        }
        current_threshold = threshold_map.get(base_tf, 0.002)
        X, Y, cleaned_df = trainer.create_multi_class_target(
            mtf_df,
            threshold=current_threshold,
            lookahead=lookahead_bars,
        )

        print("--- 三元分類標籤分佈 ---")
        print(Y.value_counts(normalize=True) * 100)
        print(f"\n總樣本數: {len(X)}")

        (
            X_train, X_val_early, X_val_cal, X_val_th, X_test,
            Y_train, Y_val_early, Y_val_cal, Y_val_th, Y_test,
        ) = trainer.time_series_split_5way(
            X,
            Y,
            train_ratio=0.60,
            val_earlystop_ratio=0.10,
            val_calibration_ratio=0.10,
            val_threshold_ratio=0.10,
            gap=20,
        )

        (
            X_train_scaled,
            X_val_early_scaled,
            X_val_cal_scaled,
            X_val_th_scaled,
            X_test_scaled,
            scaler,
        ) = trainer.normalize_features_5way(
            X_train,
            X_val_early,
            X_val_cal,
            X_val_th,
            X_test,
        )

        base_model = trainer.train_xgboost_model_v4(
            X_train_scaled,
            Y_train,
            X_val_early_scaled,
            Y_val_early,
        )

        calibrated_model = trainer.calibrate_model(
            base_model,
            X_val_cal_scaled,
            Y_val_cal,
        )

        best_thresholds = trainer.find_best_thresholds_on_val(
            calibrated_model,
            X_val_th_scaled,
            Y_val_th,
        )

        final_preds, final_probabilities = trainer.final_blind_test(
            calibrated_model,
            X_test_scaled,
            Y_test,
            short_threshold=best_thresholds["short"],
            long_threshold=best_thresholds["long"],
        )

        threshold_tag = f"{th:.3f}".rstrip('0').rstrip('.')
        joblib.dump(calibrated_model, f"calibrated_xgb_model_{threshold_tag}.pkl")
        joblib.dump(scaler, f"robust_scaler_{threshold_tag}.pkl")
        joblib.dump(X_train.columns.tolist(), "feature_columns.pkl")
        joblib.dump(best_thresholds, f"decision_thresholds_{threshold_tag}.pkl")

        print("✅ 嚴格盲測完成！檔案已匯出。")


if __name__ == "__main__":
    train()
