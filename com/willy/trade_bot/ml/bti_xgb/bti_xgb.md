# BTI XGB V1 Spec

本文件只記錄 `bti_xgb_v1_model_trainer.py` 目前這個訓練版本的實驗規格與可調項目。

不展開一般 ML 流程說明，例如特徵縮放、一般 normalization 概念、常見模型基礎知識。

## 1. Experiment Entry

- Trainer file: `com/willy/trade_bot/ml/bti_xgb_v1/bti_xgb_v1_model_trainer.py`
- Default entrypoint: `train(experiment_name="default_experiment", start_dt=None, end_dt=None)`
- Script mode default:
  - `experiment_name="baseline_v1"`

## 2. Data Scope

- Exchange: `BINANCE`
- Product: `BTCUSDT`
- Market type: `FUTURE`
- Timeframes:
  - `15m`
  - `1h`
  - `4h`
  - `1d`
- Default training window:
  - `start_dt = 2024-03-01 00:00:00+00:00`
  - `end_dt = datetime.now()` (dynamic)
- Base timeframe for training and labeling:
  - `15m`
- Dynamic Features:
  - `log_return`, `rsi_14`, `macd_hist`, `kdj_j`, `cci_14`, `vol_pct_change`, `bb_percent_b`, `vwap_bias`, `obv_diff`, `mfi_14` (Added)

可調項目：

- `start_dt`
- `end_dt`
- 交易商品
- 市場類型
- 參與 join 的 timeframe 組合
- base timeframe

## 3. Labeling Spec

- Label type: 3-class
  - `-1 = Short`
  - `0 = Hold`
  - `1 = Long`
- Label horizon:
  - `lookahead = 4`
- Barrier type:
  - ATR-based dynamic barrier
- Default ATR multiplier:
  - `atr_multiplier = 1.5`
- Current decision rule:
  - 逐根檢查未來 `lookahead` 根 K 線
  - 先碰上界標 `Long`
  - 先碰下界標 `Short`
  - 同根同時碰上下界標 `Hold`
  - 若都沒碰，則以 horizon 結束時計算 timeout return，label 為 `Hold`

可調項目：

- `DEFAULT_LOOKAHEAD`
- `DEFAULT_ATR_MULTIPLIER`
- barrier 公式
- same-bar conflict rule
- timeout rule

## 4. Model Spec

- Base model:
  - `xgboost.XGBClassifier`
- Current objective:
  - `multi:softprob`
- Number of classes:
  - `3`
- Current hyperparameters:
  - `n_estimators = 1500`
  - `early_stopping_rounds = 50`
  - `max_depth = 6`
  - `learning_rate = 0.05`
  - `subsample = 0.8`
  - `colsample_bytree = 0.8`
  - `random_state = 42`
  - `n_jobs = -1`
  - `eval_metric = "mlogloss"`
- Class weighting:
  - `compute_sample_weight(class_weight="balanced", y=y_train_mapped)`

可替換模型：

- `XGBClassifier`
- 其他 tree-based classifier
- 其他支援 `predict_proba()` 的 3-class classifier

可調項目：

- `n_estimators`
- `early_stopping_rounds`
- `max_depth`
- `learning_rate`
- `subsample`
- `colsample_bytree`
- `eval_metric`
- 類別權重策略

## 5. Calibration Spec

- Current calibration:
  - `CalibratedClassifierCV`
  - `method = "isotonic"`
- Compatibility handling:
  - 新版 sklearn 使用 `FrozenEstimator(...), cv=None`
  - 舊版 sklearn fallback 到 `cv="prefit"`

可調項目：

- calibration on/off
- calibration method
  - `isotonic`
  - `sigmoid`
- calibration dataset 區段

## 6. Validation Split Spec

- Split style:
  - `Train / Val(Early Stop) / Val(Calibration) / Val(Threshold) / Test`
- Current ratios:
  - `Train = 60%`
  - `Val(Early Stop) = 10%`
  - `Val(Calibration) = 10%`
  - `Val(Threshold) = 10%`
  - `Test = remaining`
- Gap rule:
  - `gap = max(lookahead, max_lag)`
- Current max lag:
  - `5`
- Current recommended gap:
  - `5`

可調項目：

- split ratios
- gap formula
- max lag depth
- 是否改成 expanding window
- walk-forward window 設定

## 7. Threshold Search Spec

- Threshold search set:
  - `[0.45, 0.50, 0.55, 0.60, 0.65, 0.70]`
- Prediction rule:
  - `p(short) > short_threshold` => `Short`
  - `p(long) > long_threshold` => `Long`
  - 都沒過 => `Hold`
  - 同時都過 => 優先取 `p(short)` 與 `p(long)` 較大者 (Stronger signal priority)
- Current selection score order:
  - `expectancy * sqrt(coverage)` (Balanced score)
  - `sharpe`
  - `total_pnl`
  - `profit_factor`
  - `total_trades`
- Minimum filters:
  - `total_trades >= 5`
  - `win_rate >= 0.40`
  - `temporal_diversity` (Span >= 3 unique hours)

可調項目：

- threshold grid
- conflict resolution rule
- minimum trade filter
- ranking objective
- 是否改成 coverage / expectancy / after-cost PnL 導向

## 8. Backtest Output Spec

- Current backtest basis:
  - 使用 label 階段預先算好的
    - `long_event_return`
    - `short_event_return`
    - `hold_event_return`
- Current fee assumption:
  - `fee = 0.0004`
- Current reported metrics:
  - `total_trades`
  - `win_rate`
  - `total_pnl`
  - `avg_pnl`
  - `sharpe`
  - `profit_factor`
  - `max_drawdown`

可調項目：

- fee
- event replay 規則
- timeout return 定義
- 交易績效指標集合

## 9. Walk-Forward Spec

- Current walk-forward style:
  - rolling window
- Current parameters:
  - `window_size_ratio = 0.8`
  - `step_size_ratio = 0.1`
- For each window:
  - 建立標籤
  - 5-way split
  - early stopping
  - calibration
  - threshold search
  - final blind test

可調項目：

- `window_size_ratio`
- `step_size_ratio`
- rolling vs expanding
- 每個 window 的 retrain 規則

## 10. Run Output

- Runtime metadata output:
  - experiment name
  - `start_dt`
  - `end_dt`
  - `lookahead`
  - `atr_multiplier`
  - `recommended_gap`
  - `base_tf`
  - `rows_after_mtf_join`
  - `walk_forward_windows`
- If walk-forward has results:
  - 由 `MLService.export_experiment_report(...)` 輸出實驗報告

可調項目：

- report format
- metadata fields
- artifact naming
- experiment naming

## 11. Most Likely Tuning Knobs

後續最可能調整的項目：

1. `lookahead`
2. `atr_multiplier`
3. XGBoost hyperparameters
4. calibration method
5. threshold grid
6. threshold selection objective
7. fee assumption
8. walk-forward window ratios
9. split ratios
10. gap formula

## 12. Notes

- 這份 spec 只描述目前 code 實際使用的訓練設定與可調項目。
- 如果 `bti_xgb_v1_model_trainer.py` 的訓練參數、threshold search、labeling 或輸出格式改動，這份文件應同步更新。
