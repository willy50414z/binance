# Financial ML step by step

本文依據 `binance_tech_idx_model_trainer.py` 的現行實作整理，不是泛用模板，而是這支訓練腳本目前實際執行的流程。

## 1. 資料抓取

- 標的：`BTCUSDT`
- 市場：`Binance FUTURE`
- 回看期間：最近 730 天
- 時框：`15m`、`1h`、`4h`、`1d`
- 原始欄位：`start_time`、`open`、`high`、`low`、`close`、`vol`

程式入口：

- `fetch_ohlcv()`

## 2. 平穩化

先在每個時框上建立：

- `log_return = ln(close_t / close_t-1)`

程式入口：

- `make_stationary()`

## 3. 技術指標計算

每個時框資料先經過：

- `append_technical_indicators(df)`

程式依賴的指標欄位來自：

- `TECHNICAL_INDICATOR_COLUMNS`

## 4. 特徵工程

### 4.1 背景特徵

先把指標轉成較穩定、可比較的比例特徵：

- `sma_7_bias`、`sma_25_bias`、`sma_99_bias`
- `ema_7_bias`、`ema_25_bias`、`ema_99_bias`
- `ema_7_25_spread`
- `adx_14`
- `atr_scaled`

其中特徵公式包含：

- `(close / sma_x) - 1`
- `(close / ema_x) - 1`
- `(ema_7 / ema_25) - 1`
- `atr_14 / close`

### 4.2 動態特徵來源

- `log_return`
- `rsi_14`
- `macd_hist`
- `kdj_j`
- `cci_14`
- `vol_pct_change`
- `bb_percent_b`
- `vwap_bias`
- `obv_diff`

其中特徵公式包含：

- `vol_pct_change = volume.pct_change()`
- `bb_percent_b = (close - bb_lower) / (bb_upper - bb_lower)`
- `vwap_bias = (close / vwap) - 1`
- `obv_diff = obv.diff()`

### 4.3 時序保護

為避免同根 K 線資訊洩漏：

- 所有背景特徵一律 `shift(1)`
- 所有動態特徵建立 `lag_1` 到 `lag_5`

最終模型欄位只保留：

- 背景特徵
- 動態特徵的 `lag_1` 到 `lag_5`

不直接餵入模型的欄位：

- `start_time`
- `open`
- `high`
- `low`
- `close`
- `vol` 或 `volume`

程式入口：

- `_validate_lag_feature_inputs()`
- `lag_features()`
- `model_feature_columns()`

## 5. 多時框特徵整合

以 `15m` 為主表，將 `1h`、`4h`、`1d` 特徵用 `pd.merge_asof(..., direction="backward")` 向後對齊。

目的：

- 只使用當下已知的高時框資訊
- 避免把未來高時框欄位提前併入

合併後再 `dropna()`，只保留四個時框特徵都齊全的資料。

程式入口：

- `merge_multi_timeframes()`

## 6. 標籤建立

目前是三元分類：

- `1`：Long
- `0`：Hold
- `-1`：Short

標籤邏輯：

- 觀察未來 `lookahead=4` 根 `15m` K 線
- `future_high = rolling(high, 4).max().shift(-4)`
- `future_low = rolling(low, 4).min().shift(-4)`
- `max_future_return = ln(future_high / close)`
- `min_future_return = ln(future_low / close)`

預設門檻：

- `15m`: `0.005`
- `1h`: `0.005`
- `4h`: `0.01`
- `1d`: `0.02`

實際訓練時因 base timeframe 是 `15m`，所以使用：

- `threshold = 0.005`

分類規則：

- Long：`max_future_return > threshold` 且 `min_future_return >= -threshold`
- Short：`min_future_return < -threshold` 且 `max_future_return <= threshold`
- 其他情況皆為 Hold

注意：

- 若同時觸及上下邊界，會被歸為 `Hold`
- 建標籤後會 `dropna()`

程式入口：

- `create_multi_class_target()`

## 7. 嚴格時序切分

目前不是單純 train/test，而是 5 段切分：

- `Train`: 60%
- `Val(Early Stop)`: 10%
- `Val(Calibration)`: 10%
- `Val(Threshold)`: 10%
- `Test`: 剩餘資料
- 每段之間加入 `gap=20`

切分順序：

`Train -> gap -> ValEarly -> gap -> ValCal -> gap -> ValTh -> gap -> Test`

目的：

- Early stopping、機率校正、決策門檻搜尋、最終測試彼此隔離
- 降低 validation 重複使用造成的 optimistic bias

程式入口：

- `time_series_split_5way()`

## 8. 特徵縮放

使用：

- `RobustScaler`

流程：

- 只在 `X_train` 上 `fit`
- 對 `X_train`、`X_val_early`、`X_val_cal`、`X_val_th`、`X_test` 做 `transform`

雖然 XGBoost 樹模型不一定需要縮放，但目前流程仍統一保留這一步。

程式入口：

- `normalize_features_5way()`

## 9. 模型訓練

使用模型：

- `xgboost.XGBClassifier`

目前主流程使用 `train_xgboost_model_v4()`：

- `objective='multi:softprob'`
- `num_class=3`
- `n_estimators=1500`
- `early_stopping_rounds=50`
- `max_depth=6`
- `learning_rate=0.05`
- `subsample=0.8`
- `colsample_bytree=0.8`
- `eval_metric='mlogloss'`
- `random_state=42`
- `n_jobs=-1`

類別不平衡處理：

- `compute_sample_weight(class_weight='balanced', y=Y_train_mapped)`

標籤映射：

- `-1 -> 0`
- `0 -> 1`
- `1 -> 2`

程式入口：

- `train_xgboost_model_v4()`

## 10. 機率校正

基礎模型訓練完成後，另外使用獨立的 `Val(Calibration)` 做校正。

目前方法：

- `CalibratedClassifierCV`
- `method='isotonic'`
- `cv='prefit'`

目的：

- 讓 `predict_proba()` 更接近可用的決策機率

程式入口：

- `calibrate_model()`

## 11. 門檻搜尋

在 `Val(Threshold)` 上分別為 `Short` 與 `Long` 搜尋最佳門檻。

候選門檻：

- `0.45`
- `0.50`
- `0.55`
- `0.60`
- `0.65`
- `0.70`

選擇規則：

- 以 precision 最大化為主
- precision 相同時，保留信號數較多者
- 若信號數小於 `min_signals=10` 則略過

程式入口：

- `_search_one_sided_threshold()`
- `find_best_thresholds_on_val()`

## 12. 最終盲測

只在 `Test` 做一次最終評估。

預測規則：

- 預設先設成 `Hold`
- `p(short) > short_threshold` 則改判 `Short`
- `p(long) > long_threshold` 則改判 `Long`
- 若同時超過，最後改回 `Hold`

目前輸出：

- `classification_report`
- 最終預測類別
- 預測機率

程式入口：

- `final_blind_test()`

## 13. 模型輸出

每次訓練會輸出：

- `calibrated_xgb_model_{threshold}.pkl`
- `robust_scaler_{threshold}.pkl`
- `feature_columns.pkl`
- `decision_thresholds_{threshold}.pkl`

## 14. 現行流程的優點

- 有做 lag，時序洩漏控制比一般隨機切分完整
- 高時框使用 backward asof merge，方向正確
- 將 early stop、calibration、threshold search、test 分開，驗證設計比單一 validation 更乾淨
- 有處理類別不平衡
- 最終決策不是直接吃 argmax，而是獨立 short/long 信心門檻

## 15. 目前仍需注意的風險

### 15.1 單次切分風險

目前只有一次 5-way split，仍可能對單一市場區間過度擬合。建議補：

- walk-forward validation
- anchored expanding window backtest
- 多個 regime 的穩定度比較

### 15.2 標籤門檻固定

`0.5% / 1% / 2%` 是固定常數，沒有隨波動度調整。高波動與低波動 regime 下，標籤分布可能明顯改變。建議改成：

- ATR-based threshold
- volatility regime adaptive threshold

### 15.3 門檻搜尋只看 precision

只用 precision 選 short/long threshold，容易得到交易次數過低但看似很準的結果。建議同時納入：

- recall
- signal coverage
- expectancy
- transaction cost 後的 PnL

### 15.4 Calibration 樣本可能不足

`isotonic` 在樣本偏少時容易過擬合，特別是三分類又拆出獨立校正集之後。建議比較：

- isotonic
- sigmoid / Platt scaling
- 不校正直接使用 softprob

### 15.5 缺少交易層驗證

目前評估主體還是分類報表，尚未直接驗證：

- 手續費
- 滑價
- 持倉重疊
- 最大回撤
- Sharpe / Sortino
- 每日或每週穩定度

### 15.6 再現性不足

資料抓取窗口來自 `datetime.now(timezone.utc)`，不同日期重跑會得到不同樣本。建議把以下資訊版本化：

- training start/end datetime
- data snapshot hash
- feature schema version
- model config

### 15.7 營運可讀性風險

程式輸出含 emoji，Windows `cp950` 主控台可能出現編碼錯誤或中斷。若要長期批次跑訓練，建議：

- 統一 UTF-8 console/logging
- 或移除非 ASCII log 字元

## 16. 下一步建議

若要把這套流程往 production 靠近，建議優先順序如下：

1. 補 walk-forward 驗證與交易回測指標
2. 把固定標籤門檻改成 ATR 或波動度自適應
3. 讓 threshold search 同時考慮 precision、coverage、PnL
4. 比較 isotonic 與 sigmoid calibration
5. 將資料期間、模型參數、特徵欄位版本化
