0) 目標與驗收標準
主要目標

大幅降低 range/盤整交易（減少虧損來源）

降低被 MA7 亂洗出場的頻率（你回測最大出血點）

在交易筆數下降的同時，提高：

Profit Factor

Sharpe/Sortino

最大回撤顯著下降（至少先從 ~70% 拉回到可接受區間）

驗收指標（建議最低門檻）

Profit factor > 1.0（至少先翻正）

最大回撤 < 35%（先把爆炸風險壓住）

range regime 的 trade 佔比明顯下降（越低越好）

1) 策略改動清單（分成 4 大模組）

每個模組都要做成「可開關 + 可調參數」，方便 hyperopt 找甜蜜點。

A. 趨勢/盤整濾網（避免 range）

MA 排列濾網（short 結構）

條件：ma7 < ma25 < ma99

開關：use_ma_stack_filter

MA 間距濾網（糾結=盤整）

定義：

d_7_25 = abs(ma7 - ma25) / close

d_25_99 = abs(ma25 - ma99) / close

條件：d_7_25 > a 且 d_25_99 > b

參數：min_ma7_ma25_gap = a, min_ma25_ma99_gap = b

開關：use_ma_gap_filter

避免貼 MA7 進場（降低被出場條件洗掉）

條件：(close - ma7)/close < -c

參數：min_price_below_ma7 = c

開關：use_price_dist_filter

B. MA7 下彎連續確認（你提的點）

定義：ma7_slope = ma7 - ma7.shift(1)

條件：ma7_slope < 0 連續 N 根

參數：ma7_downtrend_candles = N（N=0 代表關）

開關：你可以直接用 N > 0 當開關

建議初始 N 候選：0 / 6 / 12 / 24（15m => 1.5h / 3h / 6h）

C. 成交量濾網（相對量）

定義：vol_ratio = volume / sma(volume, vol_window)

條件（先做成兩種模式）：

模式1：vol_ratio < vol_ratio_max（避開爆量亂洗）

模式2：vol_ratio_between_low_high

參數：

vol_window

vol_ratio_max

vol_ratio_low, vol_ratio_high

開關：use_volume_filter + volume_filter_mode

D. 出場防洗（你要新增的 3K > MA7 才出）

你要的出場條件我建議做成「兩段式可選」：

出場條件 1（原本）：close > ma7 即出

開關：exit_on_close_above_ma7

出場條件 2（新增）：連續 3 根 close > ma7 才出

開關：exit_on_3c_above_ma7

參數（可做成可調）：exit_ma7_confirm_candles（預設 3，hyperopt 也可以讓它試 2~6）

注意：兩個出場條件要避免同時啟用造成邏輯重複。建議做成「模式」：

exit_mode = "ma7" 或 "ma7_confirm"

2) 具體實作要點（Freqtrade 策略內怎麼寫）
2.1 指標計算

你會需要：

ma7, ma25, ma99

ma7_slope

d_7_25, d_25_99

vol_sma, vol_ratio

above_ma7 = close > ma7

above_ma7_streak（連續計數）

above_ma7_streak 常見做法（概念）：

若 above_ma7 為 True，streak = 前一根 streak + 1

否則 streak = 0
（實作你可用 pandas 的 groupby/cumsum 技巧或自己寫）

2.2 出場信號（你要的 3 根確認）

在 populate_exit_trend()（或你用 custom_exit 的話）：

exit_mode == "ma7"：

exit = close > ma7

exit_mode == "ma7_confirm"：

exit = above_ma7_streak >= exit_ma7_confirm_candles