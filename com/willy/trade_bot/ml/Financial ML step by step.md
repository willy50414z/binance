## 核心目標

從傳統「硬規則」技術分析，轉向以「資料驅動」的機器學習模型，實現自動化決策與量化交易。

---

## 第一階段：特徵工程與數據架構 (Data Foundation)

*重點：解決數據平穩性、標籤化與偏誤問題。此階段順序至關重要。*

### 1. 數據獲取 (Fetch)

- **Binance API 接入：** 抓取不同時區（15m, 1h, 4h, 1d）的 OHLCV 原始數據。

### 2. 技術指標計算 (Technical Indicators)

- **原始價格驅動：** 在各時區獨立使用原始價格計算 RSI, MACD, Bollinger Bands 等指標。
- **原因：** 技術指標公式基於價格絕對值，若先做平穩化會導致指標失真。
- **本階段禁止特徵滯後：** 除了指標公式內部使用前值（如 `log_return = ln(Pt/Pt-1)`）外，不對特徵做 `.shift()`。
- **基礎平穩特徵：** 可在此階段同步產出 `log_return`，但保留「當期值」，統一在滯後步驟再做防洩漏處理。

| 指標分類                 | 指標名稱 (縮寫)           | 邏輯說明與 ML 特徵用途                                              |
|:---------------------|:--------------------|:-----------------------------------------------------------|
| **趨勢型 (Trend)**      | **SMA/EMA** (移動平均)  | 判斷長線方向。ML 常計算 `Close / EMA` 的乖離率作為特徵。                      |
|                      | **MACD** (平滑異同平均)   | 捕捉動能轉向。常取 `Histogram` 的斜率來預測趨勢反轉。                          |
|                      | **ADX** (平均趨向指數)    | 衡量趨勢強度（不論漲跌）。幫助模型分辨目前是「趨勢」或「盤整」。                           |
| **動能型 (Momentum)**   | **RSI** (相對強弱指標)    | 區間為 0-100。ML 常用來識別超買超賣與背離訊號。                               |
|                      | **Stochastic (KD)** | 反映價格在一段時間內的相對位置。對短線轉折預測極佳。                                 |
|                      | **CCI** (順勢指標)      | 衡量價格是否偏離平均值。常用於捕捉極端波動。                                     |
| **波動型 (Volatility)** | **Bollinger Bands** | 觀察壓力與支撐。常計算 `(Close - LowerBand) / (Upper - Lower)` 進行歸一化。 |
|                      | **ATR** (平均真實波幅)    | 衡量市場波動劇烈程度。常作為動態止損或特徵縮放 (Scaling) 的基組。                     |
| **量能型 (Volume)**     | **OBV** (能量潮)       | 利用成交量驗證價格走勢。量價背離是 ML 模型很重要的輸入。                             |
|                      | **VWAP** (成交量加權平均)  | 機構法人的參考基準。價格相對於 VWAP 的位置具有強大的支撐壓力意義。                       |
|                      | **MFI** (資金流量指標)    | 結合量能與 RSI 邏輯。判斷資金流入或流出的強度。                                 |

### 3. 滯後特徵 (Lagged Features)：

如同之前討論的，給模型 RSI_t, RSI_t-1, RSI_t-2... 到 RSI_t-5。這能讓模型學到「動能正在減弱」還是「加速噴發」。

#### a. 「偏離度」與「差值」特徵轉換表

在進行任何滯後（Lagging）之前，應先將絕對數值轉換為相對關係。

| 分類       | 原始欄位                               | 建議轉換公式 (Feature Engineering)        | 特徵意義                         |
|:---------|:-----------------------------------|:------------------------------------|:-----------------------------|
| **均線乖離** | `sma_7, 25, 99`<br>`ema_7, 25, 99` | `(close / ma) - 1`                  | **乖離率**：價格相對於均線的偏離百分比。       |
| **通道位置** | `bb_upper, lower`                  | `(close - lower) / (upper - lower)` | **%B (百分比帶)**：價格在布林通道間的相對高度。 |
| **波動縮放** | `atr_14`                           | `atr_14 / close`                    | **相對波幅**：消除絕對價格影響後的市場波動率。    |
| **基準偏離** | `vwap`                             | `(close / vwap) - 1`                | **成本偏離**：當前價格相對於成交加權平均成本的盈虧。 |
| **量能增量** | `obv`                              | `obv.diff()`                        | **能量流向**：計算該週期內資金是淨流入還是淨流出。  |
| **快慢線差** | `ema_7, ema_25`                    | `(ema_7 / ema_25) - 1`              | **趨勢發散**：短期與長期趨勢線的開口程度。      |

---

#### b. 特徵滯後 (Lagging) 處理清單

**核心規則**：所有入模特徵必須執行至少 `shift(1)` 以確保模型不會「偷看」當前 K 線的結果。
**實作等價性**：先對全部入模特徵做 `shift(1)`，再對動態特徵展開 `Lag 2~5`，等價於直接生成動態特徵的 `Lag 1~5`。

| 處理類別             | 包含欄位                                                                                                                              | 建議動作                 | 目的                  |
|:-----------------|:----------------------------------------------------------------------------------------------------------------------------------|:---------------------|:--------------------|
| **排除 (Exclude)** | `start_time`, `open`, `high`, `low`, `close`                                                                                      | 不進入模型訓練              | 原始價格不具平穩性，僅作計算基準。   |
| **背景特徵**         | `sma_7_bias`, `sma_25_bias`, `sma_99_bias`, `ema_7_bias`, `ema_25_bias`, `ema_99_bias`, `ema_7_25_spread`, `adx_14`, `atr_scaled` | 僅執行 `shift(1)`       | 提供大時區或環境背景，不需過多歷史點。 |
| **動態特徵**         | `log_return`, `rsi_14`, `macd_hist`, `kdj_j`, `cci_14`, `vol_pct_change`, `bb_percent_b`, `vwap_bias`, `obv_diff`                 | 產生 `Lag 1` 到 `Lag 5` | 捕捉短線動能變化的「形狀」與「趨勢」。 |

### c. 正規化實作檢核表

1. **先做 Train/Test Split**：務必先拆分資料，避免測試集的資訊洩漏到訓練集的 Scaler 中。
2. **需正規化欄位**：
    - 所有轉換後的 Bias 欄位 (`ema_bias`, `vwap_bias`)
    - 所有的 Lagging 特徵 (`rsi_lag1`, `log_return_lag1` 等)
    - 成交量變動與 ATR 縮放值
    - MACD 柱狀圖數值
3. **推薦 Scaler**：
    - 震盪類 (RSI, KD)：`MinMaxScaler`
    - 動能與收益類 (Log Return, Vol)：`RobustScaler` 或 `StandardScaler`
4. **Fit/Transform 規則**：
    - 只對訓練集執行 `scaler.fit(train_X)`
    - 以同一組參數做 `transform(train_X)` 與 `transform(test_X)`
    - 禁止在完整資料或測試集上 `fit`，避免 Data Leakage

#### d. 推薦實作流程 (Pipeline)

1. **[指標計算]**：利用原始價格算出所有技術指標。
2. **[基礎平穩]**：產出 `log_return = ln(Pt/Pt-1)`（此時不做額外 shift）。
3. **[特徵轉換]**：執行偏離度與差值轉換（例如：`ema_bias`, `bb_percent_b`, `vwap_bias`, `obv_diff`）。
4. **[消除偏誤]**：將所有入模特徵統一執行 `.shift(1)`。
5. **[產生滯後]**：針對動態特徵繼續產生 `_lag2` 至 `_lag5`（連同前一步可形成完整 `lag1~lag5`）。
6. **[定義標籤 Y]**：
    - 回歸：`y = log_return.shift(-1)`（用當前特徵預測下一根報酬）
    - 分類：`y = 1 if future_return > 0 else 0`（或依固定盈虧比規則）
7. **[清理空值]**：在特徵 lag 與標籤 shift 完成後，統一 `dropna()`。
8. **[時間切分]**：依時間序列切分（例如前 80% 訓練、後 20% 測試）。
9. **[正規化]**：只在訓練集 `fit`，再對 train/test 同參數 `transform`。

### 4. 定義預測目標 (Target Labeling)

- **核心原則：** 使用 `shift(-1)` 將未來結果對齊到當前特徵，形成 `X_t -> Y_{t+1}`。
- **執行時機：** 完成特徵轉換與 lag 後再建立標籤，最後再統一 `dropna()`。

#### A. 回歸目標 (Regression)

```python
# 預測下一根 K 線的對數收益率
df["target_return"] = np.log(df["close"].shift(-1) / df["close"])
```

#### B. 二元分類目標 (Binary Classification)

```python
# 下一根 K 線收盤價大於當前收盤價為 1 (漲)，否則為 0 (跌)
df["target_trend"] = (df["close"].shift(-1) > df["close"]).astype(int)
```

#### C. 三元分類目標 (Multi-Class)

```python
threshold = 0.002  # 例如 0.2% 的漲跌幅才算數

# 計算未來的實際收益率
future_return = np.log(df["close"].shift(-1) / df["close"])

# 分配標籤：1 (做多), -1 (做空), 0 (觀望)
df["target_action"] = 0
df.loc[future_return > threshold, "target_action"] = 1
df.loc[future_return < -threshold, "target_action"] = -1
```

#### 實作注意事項

1. 標籤只能使用未來資料（`shift(-1)`），不可混入當期或未滯後特徵。
2. `dropna()` 必須在「特徵 lag + 標籤位移」都完成後才執行。
3. 若使用分類閾值，建議把手續費與滑點納入 `threshold` 設計。

### 5. 嚴格按時間切分資料 (Train/Test Split)

時間序列資料絕對不能用隨機抽樣 (Random Split)，必須按時間先後切（例如前 80% 訓練，後 20% 測試）。

```python
split_idx = int(len(df) * 0.8)

X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
Y_train, Y_test = Y.iloc[:split_idx], Y.iloc[split_idx:]
```

### 5. 特徵歸一化 (Normalization)：

原因：機器學習模型（如 SVM 或神經網路）對數值大小很敏感。

作法：RSI 這種 0-100 的可以直接用，但像是 EMA 或價格，建議轉成「百分比變化」或「與價格的差值率」。

```python
from sklearn.preprocessing import RobustScaler

scaler = RobustScaler()

# ⚠️ 注意：只在 Train data 上 fit_transform
X_train_scaled = scaler.fit_transform(X_train)

# ⚠️ 注意：在 Test data 上只能 transform (沿用 Train 的參數)
X_test_scaled = scaler.transform(X_test)
```

### 6. 數據平穩化 (Stationary)

- **對數收益率 (Log Returns)：** 將價格轉換為 rt=ln(Pt/Pt−1)，確保模型學習的是變動規律而非絕對價格。
- **分數階微分 (FracDiff)：** （進階選用）在保持平穩性的同時保留更多歷史記憶。

### 7. 消除偏誤 (Lagging)

- **特徵滯後：** 將所有「特徵列」（指標、Log Returns）執行 `.shift(1)`。
- **目的：** 確保 t 時間點的模型只能看到 t−1 結算的資訊，防止前視偏誤（Look-ahead Bias）。

### 8. 多時區整合 (Multi-Timeframe Join)

- **主從結構：** 以 15m 為主表，利用 `pd.merge_asof` 將高時區（1h, 4h, 1d）的**已滯後特徵**併入。
- **前向填充：** 高時區資料在未更新前使用 `ffill()` 延續。

### 9. 進階標籤化：三欄式標籤 (Triple Barrier Method)

- **動態波動率：** 基於 15m 價格計算滾動標準差（或 ATR）以定義邊界。
- **設定三道邊界：**
    1. **上軌 (Profit-Take)：** 觸發止盈標記為 `1`。
    2. **下軌 (Stop-Loss)：** 觸發止損標記為 `1`。
    3. **時間軌 (Vertical Barrier)：** 設定持有上限 T，到期未觸及軌道標記為 `0`（或根據當下損益決定）。

### 10. 資料清理與存儲

- **缺失值處理：** 統一清理計算初期產生的 `NaN`。
- **高效存儲：** 建議儲存為 **Parquet** 格式，支持 Schema 且讀寫極快。

---

## 第二階段：模型訓練與架構選擇 (Modeling)

*重點：選擇適合表格數據的模型，並防止過擬合。*

### 1. 模型選型

- **首選：集成樹模型 (Boosting)：** 學習 `XGBoost` 或 `LightGBM`，處理結構化數據表現最穩。
- **特徵縮放：** 針對非樹狀模型（如 NN）需透過 `StandardScaler` 確保指標權重一致。

### 2. 驗證機制

- **Time-Series Split：** 遵循時間順序分割數據，不可隨機打亂。
- **Purged Cross-Validation：** 在訓練與測試集間加入 **Gap (冷卻期)**，消除序列相關導致的數據洩漏。

---

## 第三階段：量化回測與績效評估 (Validation)

*重點：模擬真實環境，驗證模型穩定性。*

### 1. 績效指標 (KPIs)

- **夏普值 (Sharpe Ratio)**、**最大回撤 (Max Drawdown)** 與 **獲利因子 (Profit Factor)**。

### 2. 整合 Freqtrade

- 將模型封裝成 `.pkl` 或 API，串接至 `Freqtrade` 策略框架進行實踐。

---

## 第四階段：自動化部署 (Engineering)

*重點：利用現有技術棧（Ubuntu, Docker, n8n）實現生產環境運行。*

### 1. 模型推論與監控

- **FastAPI / Docker：** 將模型包裝成 API 供機器人調用。
- **n8n 監控：** 當模型輸出高勝率訊號或發生**概念漂移 (Concept Drift)** 時，發送通知。
