
# 🛠️ AMRS 2.2 策略程式碼優化與修正清單

## 1. 關鍵邏輯修正 (必做)

這是目前最嚴重的問題。您辛苦寫的 `cond_full`（包含所有 ATR 與動態中軸過濾）在最後被忽略了。

* **現狀 (Line 144-147)：**
  **Python**

  ```
  cond_full = cond_env & cond_signal & cond_execution
  cond_basic_short = cond_trend_alignment & cond_A
  dataframe.loc[cond_basic_short, 'enter_short'] = 1  # 這裡只用了最基礎的條件
  ```
* **優化修正：**
  **Python**

  ```
  # 應改為執行完整過濾條件
  dataframe.loc[cond_full, 'enter_short'] = 1
  ```

  * **預期效果：** 雖然交易次數會再次下降，但每一筆交易的**質量（勝率）**會顯著提升，因為它包含了您設計的 Phase 1-3 所有濾網。

---

## 2. 落實動態 ATR 風控 (風控升級)

目前您的 `custom_stoploss` 是固定數值，這在波動大的加密貨幣市場會導致「波動小時止損太遠，波動大時被隨機掃出場」。

* **優化方向：**
  在 `populate_indicators` 中計算一個特定的止損位，並在 `custom_stoploss` 中動態調用。
* **具體實作建議：**
  **Python**

  ```
  # 在 custom_stoploss 中
  def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                      current_rate: float, current_profit: float, **kwargs) -> float:
      # 取得進場時的 ATR 或 H_rebound
      # 建議實作：stoploss = (H_rebound + 1.2 * ATR) / entry_price - 1
      return -0.05 # 目前先維持，但建議改為基於 ATR 計算的小數
  ```

---

## 3. 分批停利與移動止盈 (獲利最大化)

目前的 `custom_exit` 只要達到 5% 就全平倉，這會讓您錯失空頭大暴跌（如 10%-20%）的波段。

* **優化建議：**
  1. **取消硬性 5% 平倉：** 改用  **ATR 追蹤止盈** 。
  2. **實作移動保本：** 當獲利達到 **$1.5 \times ATR$** 時，將止損移至 **進場成本價** ，確保該筆交易不再虧損，然後放手讓利潤跑。

---

## 4. 進場價格優化 (避免追空)

目前的策略是在訊號出現當下就進場（市價或當前價），但回抽測試的核心在於「確認下跌動能回歸」。

* **優化建議：**
  在 `get_entry_price` 或 `custom_entry_price` 中設定。
  * **邏輯：** 不要一出現訊號就空，而是掛一個 **Stop-Limit Order** 在「前一根 K 棒低點」或「動態中軸」下方。
  * **預期效果：** 避免在價格還在均線附近反覆震盪時就進場，減少被掃損的機率。

---

## 5. 轉換為 Hyperopt 參數化 (解決不確定性)

為了避免下次修改又要重新跑回測，請將寫死的數值轉為參數。

* **需參數化的項目：**
  * `consolidation_amplitude_ratio`: (2.0 到 5.0)
  * `volatility_compression_ratio`: (0.8 到 2.0)
  * `upper_shadow_ratio`: (0.5 到 1.2)
  * `ma25_offset_exit`: (1.0 到 1.05)
