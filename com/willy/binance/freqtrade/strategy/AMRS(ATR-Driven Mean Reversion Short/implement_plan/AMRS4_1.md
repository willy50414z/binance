策略規格書：BTC 下跌波段空單策略 (Short-Only)

版本： 2.0 (含 MA25 與 MA99 過濾)
適用工具： Freqtrade
時框 (Timeframe)： 15m
1. 指標定義 (Indicators)

需在 populate_indicators 中定義以下指標：

    MA7: 7-period Simple Moving Average (SMA).

    MA25: 25-period Simple Moving Average (SMA).

    MA99: 99-period Simple Moving Average (SMA).

    MA7 Slope: 當前 MA7 減去前一根 MA7 的值（用於判斷斜率）。

    Consecutive_Closes: 計算價格連續收在 MA7 之上的次數。

2. 進場邏輯 (Entry Signals - Short Only)

Signal 1 (趨勢確認進場):

    close < ma7

    ma7 斜率 < 0 (MA7 下彎)

    close < ma99 (長線空頭過濾)

Signal 2 (反彈失敗再次進場):

    前一根 high 曾觸及或接近 ma7，但 close 最終低於 ma7。

    ma7 斜率保持為負。

    close < ma99。

3. 出場邏輯 (Exit Signals)

Signal 3 (常規趨勢止盈/止損):

    條件： 當價格連續 3 根 K 棒的收盤價（close）均高於 ma7。

    目的： 捕捉下跌動能衰竭。

Signal 4 (強制出場/硬止損):

    條件： 當 close 突破並收盤高於 ma25。

    目的： 當中期趨勢反轉時立即撤退，保護利潤。

4. 策略參數 (Hyperparameters)
Python

# 建議初始參數
buy_params = {
    "ma7_len": 7,
    "ma25_len": 25,
    "ma99_len": 99,
}

exit_params = {
    "exit_confirm_candles": 3,  # Signal 3 所需的連續 K 棒數
}

stoploss = -0.10  # 原始止損（作為最後防線）