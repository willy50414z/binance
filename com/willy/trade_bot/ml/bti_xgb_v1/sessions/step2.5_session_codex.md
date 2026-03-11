# Step 2.5 Session Codex

Review target:

- `com/willy/trade_bot/ml/binance_tech_idx_model_trainer.py`
- `com/willy/trade_bot/ml/step2.4_session_gemini.md`
- `com/willy/trade_bot/ml/step2.3_session_codex.md`

Review goal:

- 驗證 `step2.4_session_gemini.md` 提到的風險事項與建議是否成立
- 以目前程式碼為準，輸出新的綜合 ML review 結論

## Overall judgment

`step2.4_session_gemini.md` 的整體收斂方向是合理的，我大致認同它把問題分成：

- label / backtest realism blocker
- decision rule mismatch
- validation hygiene / reproducibility

這一輪 Gemini 的判斷比前幾輪更接近真正應執行的修正順序。

我保留的兩個補充是：

1. `gap` 與 `datetime.now()` 都是重要問題，但 Gemini 把它們放在同一個「validation hygiene & reproducibility」桶內，容易淡化它們本質上是兩種不同風險。
2. calibration 雖然被放進 Phase 2，但從目前這支程式的用途來看，因為 threshold 決策直接依賴機率，它的重要性其實已接近 blocker。

## 1. Risk validation

### 1.1 Leakage or correctness risk

- [v] **Label & Backtest Realism 是 blocker**
  - `create_multi_class_target()` 仍不是 first-touch / triple-barrier。
  - `run_backtest_stats()` 仍不是 event-driven replay。
  - 這兩個問題會同時污染 label semantics 與交易績效解讀，Gemini 把它們視為 blocker 是正確的。

- [v] **Decision Rule Mismatch 是高優先**
  - `find_best_thresholds_on_val()` 是分開對 short / long 做 one-sided threshold search。
  - `final_blind_test()` 則同時套用 short / long threshold，並在衝突時改成 `Hold`。
  - 這兩者不是同一個 optimization problem，所以 Gemini 把它升成 high priority 是合理的。

- [ ] **Threshold conflict handling 本身也可能造成額外 bias**
  - `final_blind_test()` 將 short/long 同時成立的樣本直接改成 `Hold`。
  - 這個規則目前沒有在 validation 上被單獨評估，也不是由明確的交易邏輯推導出來。
  - 即使之後把 threshold search 改成 joint optimization，仍需要決定衝突樣本到底應該 `Hold`、取較高置信方向、還是依 margin 處理。

### 1.2 Validation risk

- [v] **Validation Hygiene & Reproducibility 是高優先**
  - `gap=20` 仍是固定常數。
  - `train()` 仍依賴 `datetime.now(timezone.utc)`。
  - 這兩項確實都成立，但建議在實作時分開管理：
  - `gap` 屬於 leakage / embargo hygiene。
  - `datetime.now()` 與 metadata 缺失屬於 reproducibility。

- [x] **Gemini 對 calibration 風險在這一版描述得太弱**
  - 原因：`step2.4_session_gemini.md` 把 calibration 幾乎退到「Phase 2 validation item」。
  - 但現在 threshold decision 是直接建立在 `predict_proba()` 上，且 `find_best_thresholds_on_val()`、`final_blind_test()` 都依賴校準後機率。
  - 所以 calibration 不是單純次要 hygiene；在這個 workflow 裡，它已經直接影響決策品質，優先級應高於一般文件維護項。

### 1.3 Trading applicability risk

- [v] **Gemini 把 event-driven backtest 與 trading metrics 綁在一起是合理的**
  - 若沒有 event-driven replay，`Profit Factor`、`MDD`、equity curve 也只是建立在 proxy PnL 上。
  - 因此應該先修回放邏輯，再補完整交易指標。

- [v] **Joint threshold optimization 的建議是合理且必要的**
  - 這不只是搜尋技巧，而是避免 validation objective 與 final decision rule 不一致。
  - 我認同 Gemini 在這版把它抬到 Phase 1。

## 2. Suggestion validation

### 2.1 Suggestions I agree with

- [v] **Phase 1 先修 labeling、backtest、joint threshold search**
  - 這三項會直接改變模型的有效性判斷。
  - 如果不先修，後續 calibration、HPO、feature analysis 都容易建立在錯誤 objective 上。

- [v] **Phase 2 補 gap linkage、固定時間範圍、metadata**
  - 這些是 validation hygiene 與 reproducibility 的必要工程化補強。
  - 實作上應至少記錄 `start_dt`、`end_dt`、lookahead、lag range、threshold、calibration method。

- [v] **更新 `Financial ML step by step.md` 是必要建議**
  - 文件現在明顯落後於 code path。
  - 這不只是美化文件，而是避免研究假設與實際流程錯位。

- [v] **uniqueness weighting、score-based ranking 放在 research enhancement 階段是合理**
  - 這兩項都有研究價值。
  - 但它們不該排在 blocker 前面。

- [x] **Feature importance 與 HPO 不應被綁成同一個最後階段包處理**
  - 原因：feature importance 偏向診斷與理解，HPO 偏向搜尋最優設定，兩者目的不同。
  - 若要排序，feature diagnostics 通常可以比 HPO 更早做，因為它有助於發現 leakage 或無效特徵。
  - 不過它們都仍低於目前的 core correctness issues。

## 3. Consolidated next actions

我建議的最終優先順序如下：

1. **修正標籤**
   - 將 `create_multi_class_target()` 改成 first-touch / triple-barrier。

2. **修正回測**
   - 將 `run_backtest_stats()` 改成 path-dependent event replay。
   - 再補 `Profit Factor`、`Max Drawdown`、equity curve。

3. **修正 threshold 決策一致性**
   - 讓 threshold search 直接優化最終 joint decision rule。
   - 同時明確定義 short/long 衝突樣本的處理規則。

4. **補 calibration 驗證**
   - 比較 `isotonic` / `sigmoid`。
   - 至少輸出 Brier score；若可行再加 reliability curve / ECE。

5. **補 validation hygiene**
   - 讓 `gap` 由 `lookahead`、最大 lag、MTF 對齊需求推導。

6. **補 reproducibility**
   - 固定 `start_dt` / `end_dt`。
   - 保存 metadata 與 artifacts。

7. **同步文件**
   - 更新 `Financial ML step by step.md`。

8. **最後才做研究增強**
   - uniqueness weighting
   - score-based ranking
   - feature diagnostics
   - HPO

## Final conclusion

`step2.4_session_gemini.md` 的主結論可以採納，而且比前一輪更接近一個可執行的修正計畫。

我最終的 ML 專家判定是：

- 真正 blocker：label semantics、event-driven backtest、joint threshold consistency
- 準 blocker：calibration validation
- 高優先工程項：gap linkage、fixed training window、artifact metadata、doc sync
- 低優先研究項：uniqueness weighting、score-based ranking、feature diagnostics、HPO

如果要開始動手改程式，現在最有價值的第一步不是調模型，而是先把 `labeling + backtest + threshold search` 三件事放到同一個一致的交易事件框架下。
