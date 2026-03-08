from datetime import datetime, timedelta, timezone

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
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

            # Keep OHLCV-focused columns for subsequent technical-indicator modeling.
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

        # Deviation/difference transforms from the lag-feature design.
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

    # 輸入 lag_features 後的 DataFrame，定義三元分類標籤，並回傳可訓練的 X/Y。

    def create_multi_class_target(self, df, threshold=0.003, lookahead=4):
        """
        產生未來 N 根 K 線的三元分類標籤 (防雙向觸發版)：
        1 : 未來 N 根 K 線內，最高價觸及目標利潤 (+threshold)，且最低價未觸及停損 (-threshold)
        -1: 未來 N 根 K 線內，最低價觸及目標利潤 (-threshold)，且最高價未觸及停損 (+threshold)
        0 : 盤整，或者「同時觸發上下邊界 (震盪過大，無法確定先後順序)」皆視為觀望

        :param threshold: 目標對數收益率閾值 (例如 0.003 代表 0.3%)
        :param lookahead: 往未來觀察的 K 線數量 (例如 15m K 線，lookahead=4 代表看未來 1 小時)
        """
        df = df.copy()

        # 1. 計算未來 N 根 K 線內的「最高價」與「最低價」
        # rolling(lookahead).max() 會找過去 N 根的最大值
        # 加上 shift(-lookahead) 就會變成把「未來的最大值」拉到當前這列
        future_high = df['high'].rolling(window=lookahead).max().shift(-lookahead)
        future_low = df['low'].rolling(window=lookahead).min().shift(-lookahead)

        # 2. 計算對應的最大上漲與最大下跌對數收益率
        df['max_future_return'] = np.log(future_high / df['close'])
        df['min_future_return'] = np.log(future_low / df['close'])

        # 3. 根據閾值進行三元分類
        df['target_action'] = 0  # 預設盤整

        # 條件：做多 (摸到上方目標，且沒有摸到下方停損/目標)
        cond_long = (df['max_future_return'] > threshold) & (df['min_future_return'] >= -threshold)

        # 條件：做空 (摸到下方目標，且沒有摸到上方停損/目標)
        cond_short = (df['min_future_return'] < -threshold) & (df['max_future_return'] <= threshold)

        df.loc[cond_long, 'target_action'] = 1
        df.loc[cond_short, 'target_action'] = -1

        # 4. 清理 NaN
        # shift(-lookahead) 會導致最後 N 筆資料變成 NaN，必須刪除
        df = df.dropna().reset_index(drop=True)

        # 5. 切出特徵 (X) 與標籤 (Y)
        # 確保把我們剛剛產生用來對答案的未來收益率排除掉
        exclude_cols = ['start_time', 'open', 'high', 'low', 'close', 'vol',
                        'max_future_return', 'min_future_return', 'target_action']

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
        # 1. 取出主表 (15m)
        base_df = ohlcv_data[base_tf].copy()

        # merge_asof 嚴格要求用來對齊的時間欄位必須是排序過的
        base_df = base_df.sort_values("start_time")

        # 2. 準備要併入的高時區清單
        higher_tfs = [tf for tf in ohlcv_data.keys() if tf != base_tf]

        for tf in higher_tfs:
            higher_df = ohlcv_data[tf].copy()
            higher_df = higher_df.sort_values("start_time")

            # 為了避免合併後出現一堆 open_1h, close_1h 這種用不到的價格欄位
            # 我們只保留 start_time 和「模型特徵欄位」
            # 修正前：
            # feature_columns = [col for col in higher_df.columns if
            #                    col not in BinanceTechIdxModelTrainer.EXCLUDED_COLUMNS]

            # 修正後 (極度精準)：
            feature_columns = self.model_feature_columns()
            higher_features = higher_df[["start_time"] + feature_columns]

            # 3. 執行 asof 合併
            # direction="backward" 是靈魂：例如 10:15 的 K 線，只能對應到 10:00 結算的 1h 特徵
            base_df = pd.merge_asof(
                base_df,
                higher_features,
                on="start_time",
                direction="backward",
                suffixes=("", f"_{tf}")  # 為高時區的欄位加上後綴，例如 rsi_14_lag_1_1h
            )

        # 4. 處理合併後早期資料的 NaN (例如 15m 的前幾根 K 線還對應不到 1d 的資料)
        base_df = base_df.dropna().reset_index(drop=True)

        return base_df

    def train_xgboost_model(seld, X_train, Y_train, X_test, Y_test):
        print("\n" + "=" * 40)
        print("🧠 開始訓練 XGBoost 模型...")
        print("=" * 40)

        # 1. 設定 XGBoost 參數 (使用預設或微調的參數)
        # 因為是 1, 0, -1 三元分類，我們要告訴模型 objective 是 multi:softmax
        # 這裡將標籤轉換為 0, 1, 2 (XGBoost 要求標籤從 0 開始)
        Y_train_mapped = Y_train.map({-1: 0, 0: 1, 1: 2})
        Y_test_mapped = Y_test.map({-1: 0, 0: 1, 1: 2})

        model = xgb.XGBClassifier(
            n_estimators=300,  # 決策樹的數量
            max_depth=6,  # 樹的深度
            learning_rate=0.05,  # 學習率
            subsample=0.8,  # 隨機抽樣比例 (防止過擬合)
            colsample_bytree=0.8,  # 特徵隨機抽樣比例
            objective='multi:softmax',
            num_class=3,
            random_state=42,
            n_jobs=-1  # 使用所有 CPU 核心
        )

        # 2. 訓練模型
        model.fit(
            X_train,
            Y_train_mapped,
            eval_set=[(X_train, Y_train_mapped), (X_test, Y_test_mapped)],
            verbose=50  # 每 50 棵樹印一次進度
        )

        # 3. 預測並評估
        predictions = model.predict(X_test)

        print("\n📊 模型測試集評估報告:")
        print(f"整體準確率 (Accuracy): {accuracy_score(Y_test_mapped, predictions):.4f}")

        # 印出詳細報告，將標籤轉回我們熟悉的 -1, 0, 1
        target_names = ['Short (-1)', 'Hold (0)', 'Long (1)']
        print("\n" + classification_report(Y_test_mapped, predictions, target_names=target_names))

        # 4. 畫出 Feature Importance (特徵重要性前 20 名)
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

        # 1. 標籤轉換為 0, 1, 2
        Y_train_mapped = Y_train.map({-1: 0, 0: 1, 1: 2})
        Y_test_mapped = Y_test.map({-1: 0, 0: 1, 1: 2})

        # 2. 自動計算樣本權重 (Sample Weights)
        # 這會讓樣本數少的類別 (-1, 1) 獲得較大的權重，樣本數多的 (0) 權重較小
        sample_weights = compute_sample_weight(class_weight='balanced', y=Y_train_mapped)

        print("已自動計算並套用類別權重 (Balanced)")

        # 3. 設定模型 (加入 early_stopping_rounds)
        model = xgb.XGBClassifier(
            n_estimators=500,  # 可以設大一點，因為有 Early Stopping 把關
            early_stopping_rounds=20,  # 連續 20 棵樹沒進步就停止
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective='multi:softmax',
            num_class=3,
            random_state=42,
            n_jobs=-1,
            eval_metric='mlogloss'  # 評估標準使用多分類對數損失
        )

        # 4. 訓練模型 (傳入 sample_weight)
        model.fit(
            X_train,
            Y_train_mapped,
            sample_weight=sample_weights,  # 👑 靈魂參數：強制模型重視做多與做空
            eval_set=[(X_train, Y_train_mapped), (X_test, Y_test_mapped)],
            verbose=50
        )

        # 取得最佳迭代次數
        best_iteration = model.best_iteration
        print(f"\n✅ Early Stopping 觸發！最佳模型停在第 {best_iteration} 棵樹")

        # 5. 預測並評估
        predictions = model.predict(X_test)

        # 👑 評估關鍵：不要只看 Accuracy，重點看 -1 和 1 的 F1-Score 和 Recall
        target_names = ['Short (-1)', 'Hold (0)', 'Long (1)']
        print("\n📊 進化版模型測試集評估報告:")
        print(classification_report(Y_test_mapped, predictions, target_names=target_names))

        # 6. 畫出 Feature Importance (可選，若你已經確認過特徵可註解掉)
        feature_importances = pd.Series(model.feature_importances_, index=X_train.columns)
        top_features = feature_importances.sort_values(ascending=True).tail(20)

        plt.figure(figsize=(10, 8))
        top_features.plot(kind='barh', color='darkorange')
        plt.title(f'Top 20 Important Features (Best Iteration: {best_iteration})')
        plt.xlabel('Importance Score')
        plt.tight_layout()
        # 把原本的 plt.show() 替換成以下代碼
        plt.tight_layout()
        # 自動用閾值或時間命名存檔 (如果你的函數沒有傳入閾值參數，可以直接存成統一名稱或加時間戳)
        plt.savefig(f'feature_importance_latest_{threshold}.png')
        plt.close()  # 關閉畫布，釋放記憶體，讓迴圈繼續！

        return model

    def train_xgboost_model_v3(self, X_train, Y_train, X_val, Y_val):
        """
        訓練 XGBoost 並使用 Validation Set 進行機率校準 (Calibration)
        注意：這裡不再傳入 X_test，徹底杜絕測試集洩漏。
        """
        print("\n" + "=" * 40)
        print("🚀 啟動 V3 機率校準版 XGBoost 模型 (Softprob + Calibration)")
        print("=" * 40)

        Y_train_mapped = Y_train.map({-1: 0, 0: 1, 1: 2})
        Y_val_mapped = Y_val.map({-1: 0, 0: 1, 1: 2})

        sample_weights = compute_sample_weight(class_weight='balanced', y=Y_train_mapped)

        # 1. 基礎模型訓練 (指定 softprob)
        base_model = xgb.XGBClassifier(
            n_estimators=1500,
            early_stopping_rounds=50,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective='multi:softprob',  # 🌟 強制輸出真實機率分佈
            num_class=3,
            random_state=42,
            n_jobs=-1,
            eval_metric='mlogloss'
        )

        base_model.fit(
            X_train, Y_train_mapped,
            sample_weight=sample_weights,
            eval_set=[(X_train, Y_train_mapped), (X_val, Y_val_mapped)],
            verbose=100
        )

        print(f"\n✅ 基礎訓練結束！最佳模型停在第 {base_model.best_iteration} 棵樹")

        # 2. 🌟 關鍵修正：機率校準 (Isotonic Calibration)
        # 因為我們用了 balanced weight，機率被嚴重扭曲。我們用 Val Set 將機率重新校準回真實比例。
        # cv="prefit" 代表使用剛剛已經練好的 base_model
        from sklearn.calibration import CalibratedClassifierCV
        calibrated_model = CalibratedClassifierCV(base_model, method='isotonic', cv="prefit")
        calibrated_model.fit(X_val, Y_val_mapped)

        print("✅ 機率校準 (Calibration) 完成！現在模型輸出的 % 數可以信任了。")

        return calibrated_model

    def normalize_features_3way(
            self, X_train: pd.DataFrame, X_val: pd.DataFrame, X_test: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, RobustScaler]:

        scaler = RobustScaler()
        # ⚠️ 永遠只能用 Train data 來 fit
        X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train), columns=X_train.columns, index=X_train.index)

        X_val_scaled = pd.DataFrame(scaler.transform(X_val), columns=X_val.columns, index=X_val.index)
        X_test_scaled = pd.DataFrame(scaler.transform(X_test), columns=X_test.columns, index=X_test.index)

        return X_train_scaled, X_val_scaled, X_test_scaled, scaler

    def time_series_split_3way(
            self,
            X: pd.DataFrame,
            Y: pd.Series,
            train_ratio: float = 0.7,
            val_ratio: float = 0.15,
            gap: int = 20  # 🌟 新增：隔離區 (確保 lookahead 和 lag 絕對不會互相污染)
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
        """
        將時序資料嚴格切分為: Train, Validation, Test，並在交界處加入 Gap (Embargo)
        """
        train_end = int(len(X) * train_ratio)
        val_start = train_end + gap
        val_end = int(len(X) * (train_ratio + val_ratio))
        test_start = val_end + gap

        X_train, Y_train = X.iloc[:train_end], Y.iloc[:train_end]
        X_val, Y_val = X.iloc[val_start:val_end], Y.iloc[val_start:val_end]
        X_test, Y_test = X.iloc[test_start:], Y.iloc[test_start:]

        print(f"嚴格切分 (含 {gap} 根 K 線 Gap) -> Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")
        return X_train, X_val, X_test, Y_train, Y_val, Y_test

    def find_best_threshold_on_val(self, calibrated_model, X_val, Y_val):
        """在 Validation Set 上尋找最佳信心門檻 (以做多的 Precision 為主)"""
        print("\n🔍 正在 Validation Set 上尋找最佳信心門檻...")
        Y_val_mapped = Y_val.map({-1: 0, 0: 1, 1: 2})
        probabilities = calibrated_model.predict_proba(X_val)
        p_long = probabilities[:, 2]

        best_th = 0.50
        best_precision = 0.0

        for th in [0.45, 0.50, 0.55, 0.60]:
            strong_long_idx = p_long > th
            if np.sum(strong_long_idx) < 10:  # 如果觸發次數太少，這門檻沒意義
                continue

            # 算出這個門檻下，做多被猜中的比例 (Precision)
            true_positives = np.sum((Y_val_mapped.values == 2) & strong_long_idx)
            precision = true_positives / np.sum(strong_long_idx)

            print(f"門檻 {th * 100}% -> 做多精準度 (Precision): {precision:.4f} | 觸發次數: {np.sum(strong_long_idx)}")

            if precision > best_precision:
                best_precision = precision
                best_th = th

        print(f"🏆 選定最佳信心門檻: {best_th * 100}%")
        return best_th

    def final_blind_test(self, calibrated_model, X_test, Y_test, best_threshold):
        """使用剛才選定的門檻，對 Test Set 進行唯一一次的絕對盲測"""
        print("\n" + "=" * 50)
        print(f"🔥 最終絕對盲測 (Test Set) - 鎖定門檻: {best_threshold * 100}%")
        print("=" * 50)

        Y_test_mapped = Y_test.map({-1: 0, 0: 1, 1: 2})
        probabilities = calibrated_model.predict_proba(X_test)

        custom_predictions = np.ones(len(probabilities))
        strong_short_idx = probabilities[:, 0] > best_threshold
        strong_long_idx = probabilities[:, 2] > best_threshold

        custom_predictions[strong_short_idx] = 0
        custom_predictions[strong_long_idx] = 2
        custom_predictions[strong_short_idx & strong_long_idx] = 1

        target_names = ['Short (-1)', 'Hold (0)', 'Long (1)']
        print(classification_report(Y_test_mapped, custom_predictions, target_names=target_names))

        return custom_predictions

    def evaluate_with_confidence(self, model, X_test, Y_test, confidence_threshold=0.50):
        """
        使用 predict_proba 取得機率，並加上自訂信心門檻過濾交易訊號。

        :param confidence_threshold: 信心門檻 (例如 0.50 代表模型要有 50% 以上的把握才出手)
        """
        print(f"\n" + "=" * 50)
        print(f"🎯 啟用機率決策模式 (信心門檻: {confidence_threshold * 100}%)")
        print("=" * 50)

        # 1. 轉換標籤以對應 XGBoost 的輸出格式 (0, 1, 2)
        Y_test_mapped = Y_test.map({-1: 0, 0: 1, 1: 2})

        # 2. 取得機率矩陣 (Shape: [樣本數, 3])
        # 欄位對應: 0 -> Short (-1), 1 -> Hold (0), 2 -> Long (1)
        probabilities = model.predict_proba(X_test)

        # 3. 建立自訂的預測陣列 (預設全部填入 1，也就是 Hold)
        custom_predictions = np.ones(len(probabilities))

        # 4. 根據信心門檻覆蓋訊號
        # 只有當 P(Short) 或 P(Long) 大於我們設定的門檻時，才真正出手
        p_short = probabilities[:, 0]
        p_long = probabilities[:, 2]

        # 找出大於門檻的 index
        strong_short_idx = p_short > confidence_threshold
        strong_long_idx = p_long > confidence_threshold

        # 將這些高信心的 index 標記為實際交易動作
        custom_predictions[strong_short_idx] = 0  # 執行做空
        custom_predictions[strong_long_idx] = 2  # 執行做多

        # (防呆) 如果模型發生極端錯誤，同時給予 Long 和 Short 極高機率，強制轉為 Hold
        conflict_idx = strong_short_idx & strong_long_idx
        custom_predictions[conflict_idx] = 1

        # 5. 印出過濾後的評估報告
        target_names = ['Short (-1)', 'Hold (0)', 'Long (1)']
        print(classification_report(Y_test_mapped, custom_predictions, target_names=target_names))

        # 6. 統計「放棄交易」的比例
        original_predictions = model.predict(X_test)
        original_trades = np.sum((original_predictions == 0) | (original_predictions == 2))
        new_trades = np.sum((custom_predictions == 0) | (custom_predictions == 2))

        print(f"💡 交易次數變化: 原本 {original_trades} 次 -> 過濾後 {new_trades} 次")
        if original_trades > 0:
            print(f"💡 訊號過濾率: {((original_trades - new_trades) / original_trades) * 100:.2f}% 的低信心訊號被捨棄")

        return custom_predictions, probabilities


def train():
    # Fetch OHLCV data.
    trainer = BinanceTechIdxModelTrainer()
    ohlcv_data = trainer.fetch_ohlcv()
    base_tf = Timeframe.MINUTE_15.value

    for timeframe, df in ohlcv_data.items():
        # Ensure stationary transform runs before technical indicators.
        df = trainer.make_stationary(df)
        df = append_technical_indicators(df)
        if df is None or df.empty:
            ohlcv_data[timeframe] = df
            print(f"{timeframe}: rows=0")
            continue

        # Build lagged features according to the lag-feature design.
        df = trainer.lag_features(df)
        df = df.dropna(subset=trainer.model_feature_columns()).reset_index(drop=True)
        ohlcv_data[timeframe] = df

    print("\n--- 執行多時區特徵整合 (MTF Join) ---")
    mtf_df = trainer.merge_multi_timeframes(ohlcv_data, base_tf=base_tf)
    print(f"整合後大表欄位數: {len(mtf_df.columns)}")
    print(f"整合後大表資料筆數: {len(mtf_df)}")

    # 測試未來 4 根 K 線，看漲/跌幅能否突破 0.3%, 0.4%, 0.5%
    test_thresholds = [0.005]
    lookahead_bars = 4

    for th in test_thresholds:
        print(f"\n\n{'=' * 50}")
        print(f"🔬 正在測試 目標利潤: {th * 100}%, 觀察期: {lookahead_bars} 根 K 線")
        print(f"{'=' * 50}")
        # 定義各時區的合理收益率閾值
        threshold_map = {
            Timeframe.MINUTE_15.value: th,  # 0.2%
            Timeframe.HOUR_1.value: 0.005,  # 0.5%
            Timeframe.HOUR_4.value: 0.01,  # 1.0%
            Timeframe.DAY_1.value: 0.02  # 2.0%
        }
        current_threshold = threshold_map.get(base_tf, 0.002)
        X, Y, cleaned_df = trainer.create_multi_class_target(mtf_df, threshold=current_threshold,
                                                             lookahead=lookahead_bars)

        # 檢查三元分類標籤分佈
        print("--- 三元分類標籤分佈 ---")
        print(Y.value_counts(normalize=True) * 100)  # 百分比分佈
        print(f"\n總樣本數: {len(X)}")

        # X_train, X_test, Y_train, Y_test = trainer.time_series_split(X, Y, split_ratio=0.8)
        # X_train_scaled, X_test_scaled, scaler = trainer.normalize_features(X_train, X_test)
        # print(
        #     f"{base_tf}: scaled train/test shape = "
        #     f"{X_train_scaled.shape}/{X_test_scaled.shape}, target shape = {Y_train.shape}/{Y_test.shape}"
        # )
        #
        # # 執行模型訓練與評估
        # model = trainer.train_xgboost_model_v2(X_train_scaled, Y_train, X_test_scaled, Y_test, th)

        # 1. 三段切分 (Train, Val, Test) 含 Gap 防洩漏
        X_train, X_val, X_test, Y_train, Y_val, Y_test = trainer.time_series_split_3way(X, Y, train_ratio=0.7,
                                                                                        val_ratio=0.15)

        # 2. 三段歸一化
        X_train_scaled, X_val_scaled, X_test_scaled, scaler = trainer.normalize_features_3way(X_train, X_val, X_test)

        # 3. 呼叫 V3 訓練 (此時只傳入 Train 和 Val，把 Test 藏好)
        calibrated_model = trainer.train_xgboost_model_v3(X_train_scaled, Y_train, X_val_scaled, Y_val)

        # 4. 在 Val 上決定最佳門檻 (看期中考卷抓重點)
        best_th = trainer.find_best_threshold_on_val(calibrated_model, X_val_scaled, Y_val)

        # 5. 在 Test 上執行最終盲測 (期末考唯一一次機會)
        final_preds = trainer.final_blind_test(calibrated_model, X_test_scaled, Y_test, best_th)

        # 6. 儲存 Calibration 過的模型
        joblib.dump(calibrated_model, "calibrated_xgb_model_0.005.pkl")  # 注意：Calibrated 模型要存成 pkl
        joblib.dump(scaler, "robust_scaler_0.005.pkl")
        joblib.dump(X_train.columns.tolist(), "feature_columns.pkl")
        print("✅ 嚴格盲測完成！檔案已匯出。")


if __name__ == "__main__":
    train()
