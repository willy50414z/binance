# Session Notes

## 開發進度

- [v] 概念討論
- [v] 實現計畫討論
- [ ] 程式調整
- [ ] 回測並檢驗績效

本次檢查對象：

- `binance_tech_idx_model_trainer.py`

## 結論

這支訓練腳本的方向比一般 baseline 好，因為已經處理了：

- lag feature 避免同根 K 線洩漏
- `merge_asof(..., direction="backward")` 避免高時框前視偏誤
- `Train / Val(Early Stop) / Val(Calibration) / Val(Threshold) / Test` 分離
- class weight 平衡
- 以機率門檻做最終交易決策

但整體仍屬於「研究版流程」，還沒有到可直接信任的 production trading pipeline。

## 主要風險

### [v] P1. 單次切分，無法證明跨 regime 穩定

目前只做一次 5-way split。即使這次 Test 表現好，也可能只是剛好對某一段 BTC 行情有效。

影響：

- 容易高估泛化能力
- 對趨勢市、震盪市、突發波動期的穩定性沒有證據

建議：

- [v] 加 walk-forward validation
- [v] 用 expanding window 重複訓練與測試
- [v] 比較不同 market regime 的結果

**專家意見：** 金融數據具有嚴重的非平穩性 (Non-stationarity)，單次切分極易陷入 Overfitting to a specific regime。必須引入 Walk-forward 或 Multi-block Cross-validation。

### [v] P1. 門檻搜尋只優化 precision，容易過濾成「很準但幾乎不交易」

`find_best_thresholds_on_val()` 目前只用 precision 排序，`min_signals=10` 太寬鬆，仍可能選到覆蓋率過低的門檻。

影響：

- 報表看起來漂亮，但策略可能沒有足夠交易數
- 實際 PnL 未必好

建議：

- [v] threshold objective 改成多目標
- [v] 同時看 precision、coverage、expectancy、after-cost PnL
- [v] 設定最低交易數或最低 coverage

**專家意見：** 過高的 Precision 通常伴隨著極低的 Recall。在交易中，這會導致交易機會過少，無法覆蓋固定成本。應考慮使用 F1-score 的變體或直接以 Expected Return 作為優化目標。

### [v] P1. 缺少交易層評估，分類好不代表能賺錢

目前最終盲測輸出是 `classification_report`，沒有交易績效指標。

影響：

- 無法知道手續費後是否仍有 edge
- 無法評估最大回撤與風險調整報酬

建議：

- [v] 在 Test 上加入簡單事件回放
- [v] 至少輸出 win rate、avg trade return、profit factor、max drawdown、Sharpe
- [v] 將交易成本與滑價納入

**專家意見：** 分類準確率 (Accuracy) 與交易損益 (PnL) 往往不完全線性相關。應在 `final_blind_test` 後串接 Equity Curve 模擬，計算 Sharpe Ratio 與 Max Drawdown。

### [v] P2. 固定標籤門檻可能對不同波動 regime 不穩

現在的標籤門檻是固定常數，base `15m` 使用 `0.005`。

影響：

- 高波動期標籤太容易觸發
- 低波動期標籤太難觸發
- 類別比例會跟著 regime 飄移

建議：

- [v] 改成 ATR-based barrier
- [v] 或用 rolling volatility 自適應門檻

**專家意見：** 這是典型的 Data Leakage 變體（雖然不是直接洩漏，但會造成樣本分佈偏移）。建議改用 $k \times \text{ATR}$ 或 $k \times \text{Rolling Volatility}$ 作為動態邊界。

### [v] P2. Label 定義沒有處理先後觸價順序

目前是看未來 4 根內的最高價與最低價是否碰到上下界。若上下界都被碰到，就直接標成 `Hold`。

影響：

- 這是保守作法，能避免誤標
- 但也會丟掉一部分原本可判定的樣本

建議：

- [v] 若要更接近交易真實性，可改成 event-driven first-touch labeling
- [v] 或直接改用 triple-barrier method

**專家意見：** 這是 Fixed-horizon labeling 的侷限。改用 Triple-barrier method 並引入 `path dependency`（即記錄觸碰邊界的順序）能更精確地捕捉交易邏輯。

### [v] P2. Calibration 使用 isotonic，資料量不足時可能過擬合

`CalibratedClassifierCV(method="isotonic", cv="prefit")` 在樣本少時通常不穩，三分類情境更明顯。

影響：

- 機率表面上更平滑，但 out-of-sample 未必更可靠

建議：

- [v] 比較 isotonic 與 sigmoid
- [v] 驗證 Brier score、ECE、reliability curve

**專家意見：** Isotonic Regression 是一種類非參數方法，容易產生階梯狀擬合。在數據量不足（例如加密貨幣高時框數據）時，Sigmoid (Platt Scaling) 通常更 Robust。

### [v] P2. gap=20 是固定常數，沒有綁定 lookahead 與最大特徵記憶長度

目前切分有 embargo/gap，這是對的；但 gap 並未與實際標籤 horizon 或高時框記憶長度連動。

影響：

- 某些情況 gap 可能不足
- 某些情況 gap 又開浪費資料

建議：

- [v] 至少令 gap >= lookahead
- [v] 視高時框與 lag 深度，重新定義 purge/embargo 長度

**專家意見：** 理想的 Gap 應該是 $\text{lookahead} + \text{max lag period}$。目前固定 20 雖暫時安全，但缺乏參數連動會導致未來調整 lookahead 時遺漏 leakage 風險。

### [v] P3. 資料品質與實驗再現性不足

目前資料抓取使用：

- `datetime.now(timezone.utc)`

影響：

- 每次重跑樣本不同
- 難以比對模型版本

建議：

- [v] 固定訓練區間
- [v] 記錄資料起訖時間
- [v] 保存特徵版本與訓練參數
- [v] 對輸出 artifacts 加 metadata

**專家意見：** 實驗再現性 (Reproducibility) 是機器學習的基石。應將 `start_dt` 與 `end_dt` 參數化，並在訓練後保存 Data Snapshot 或其 Hash。

### [v] P3. Windows 主控台可能因 emoji/編碼中斷輸出

程式本身能編譯，但在 `cp950` 主控台輸出 emoji 會出現 `UnicodeEncodeError`。

影響：

- 訓練 log 不穩
- 批次執行或排程時可能中斷

建議：

- [v] 改用 logging 並強制 UTF-8
- [v] 或移除 emoji

**專家意見：** 雖然是工程小細節，但在 Windows 環境下是常見的 Crash 點。建議封裝一個支援 UTF-8 的 Logger。

## 建議優先順序

- [ ] 1. 補 walk-forward 與交易績效驗證
- [ ] 2. 調整 threshold search objective，不只看 precision
- [ ] 3. 把固定 barrier 改成波動度自適應
- [ ] 4. 比較 isotonic / sigmoid calibration
- [ ] 5. 補 metadata 與 artifact versioning
- [ ] 6. 清理 log 編碼問題

## 如果下一輪要直接改程式

最值得先做的三件事：

1. [ ] 在 `final_blind_test()` 後新增簡單回測統計
2. [ ] 新增 walk-forward runner，重複產生多段 out-of-sample 結果
3. [ ] 將 `create_multi_class_target()` 改成 ATR-based barrier

## 2026-03-11 CODEX Review 補充

- 已輸出 review: `bti_xgb_v1/sessions/20260311174620_CODEX.md`
- 補充結論：
  - 本次問題不只是不平衡，也可能是 label density 過低與 raw ranking power 不足
  - `best_iteration = 4` 與 `thresholds.json = {0.5, 0.5}` 顯示 validation 階段很可能沒有形成可交易候選
  - 下一步應先補 diagnosis report，而不是直接擴大 threshold 或深調超參數
- 建議優先項：
  1. [ ] 輸出各 window 的 label / prediction / probability 分布
  2. [ ] 系統性掃 `lookahead` 與 `atr_multiplier`
  3. [ ] 比較 raw / no calibration / sigmoid / isotonic

## 2026-03-11 CODEX Review 補充 2

- 已輸出 review: `bti_xgb_v1/sessions/20260311175639_CODEX.md`
- 新增重點：
  - `find_best_thresholds_on_val()` 在沒有 valid candidate 時會靜默回退到 `0.50 / 0.50`，這必須顯式標記，不能當成最佳 threshold
  - walk-forward 評估後保存的是最後一個 window 的 model bundle，不適合直接視為 deployment artifact
  - calibration 若改成 cross-validation，必須使用 time-series split，不能用隨機 CV
- 下一步：
  1. [ ] 在報表加入 fallback threshold 與 candidate 數量
  2. [ ] 補 raw vs calibrated ranking 對照
  3. [ ] 定義 deployment 前的 final refit 流程

## 2026-03-11 CODEX Review 補充 3

- 已輸出 review: `bti_xgb_v1/sessions/20260311182316_CODEX.md`
- 本輪結論：
  - 同意主診斷方向是 signal starvation，但不同意把 `total_trades >= 5` 直接放寬到 `>= 1` 當正式 threshold 選擇規則
  - `val_earlystop` 與 `val_cal` 可暫時合併做診斷，但需標示為 diagnostic mode，避免和正式 calibration 結論混用
  - `learning_rate=0.01` 不應列高優先，先補 candidate/fallback/probability collapse 的完整診斷
- 新增建議：
  1. [ ] 將 threshold search 拆成 diagnostic mode 與 production selection mode
  2. [ ] 補 `candidate_count`、`fallback_used`、`max_prob mean/std`、`best_iteration`
  3. [ ] 掃 `lookahead x atr_multiplier`，不要只單改其中一個
