# Freqtrade Backtesting Guide (Ma725BreakStrategy)

本文件說明如何使用 Freqtrade 框架執行 `Ma725BreakStrategy` 的回測與績效分析。

## 1. 環境準備

確保您在專案根目錄 `e:\code\binance` 下執行指令，且已正確配置 `config.json`。

`freqtrade create-userdir --userdir com\willy\binance\freqtrade\user_data`

### 必備檔案

- 策略檔案：`com/willy/binance/freqtrade/Ma725BreakStrategy.py`
- 設定檔案：`config.json` (已配置 futures 模式與 BTC/USDT:USDT 交易對)

---

## 2. 執行步驟

### 第一步：下載歷史數據

在開始回測前，必須先從交易所下載 K 線數據。

```powershell
.\venv\Scripts\freqtrade.exe download-data `
    --config config.json `
    --days 300 `
    --timeframes 15m `
    --trading-mode futures
```

### 第二步：執行回測

執行策略並計算績效指標。

```powershell
.\venv\Scripts\freqtrade.exe backtesting `
    --strategy Ma725BreakStrategy `
    --strategy-path ./ `
    --config config.json `
    --timerange 20250101- `
    --timeframe 15m `
    --export trades
```

*參數說明：*

- `--timerange 20250101-`: 從 2025 年 1 月 1 日開始測試至今。
- `--export trades`: 匯出詳細交易歷史以供後續分析或繪圖。

### 第三步：產出視覺化報告 (Plot)

將回測結果轉換為互動式網頁圖表，方便觀察買賣點位。

```powershell
.\venv\Scripts\freqtrade.exe plot-dataframe `
    --strategy Ma725BreakStrategy `
    --strategy-path ./ `
    --config config.json `
    --indicators1 ma7,ma25 `
    --indicators2 rsi
```

*檔案位置：* 產出的 HTML 檔案會存放在 `user_data/plot/` 目錄下。

---

## 3. 核心指標說明

回測完成後，請重點關注 **STRATEGY SUMMARY** 中的以下數據：

- **Win Rate**: 勝率。
- **Profit Factor**: 獲利因子 (應 > 1.0)。
- **Drawdown**: 最大回撤，衡量策略下行風險。
- **Sharpe Ratio**: 風險調整後回報。

## 4. 常見問題排除 (Debug Log)

- **錯誤：Configuration error: 'pairlists' is a required property**
    - 解決：已在 `config.json` 中加入 `"pairlists": [{"method": "StaticPairList"}]`。
- **錯誤：KeyError: 'exit_pricing'**
    - 解決：已在 `config.json` 中補齊 `entry_pricing` 與 `exit_pricing` 區塊。
- **錯誤：Invalid URL (Futures Pair Name)**
    - 解決：期貨模式下交易對必須使用 `BTC/USDT:USDT` 格式。
