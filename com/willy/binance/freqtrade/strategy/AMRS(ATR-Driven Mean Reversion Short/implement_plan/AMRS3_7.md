✅ 本次回測實際使用條件（AMRS3_7 預設參數）
基本設定
項目 設定
Timeframe 15m
方向 Short only
minimal_roi 0 → 100（實質不使用 ROI）
use_exit_signal False（只用 custom_exit）
初始 stoploss -5%
🟢 進場條件（本次回測實際生效條件）
1️⃣ 趨勢結構（必要）

必須同時成立：

close < MA7

MA7 < MA25

MA25 < MA99

MA25 slope < 0

MA99 slope < 0

2️⃣ 盤整濾網（有啟用）

因為：

enable_consolidation_filter = 1

必須同時成立：

(high_20 - low_20) / ATR < 2.8

close_std_20 / ATR < 0.95

3️⃣ Break 模式（本次使用 low10 模式）

因為：

break_mode = 0
break_atr_buffer = 0.2

所以使用：

break_level = low_10 - 0.2 * ATR

進場需：

close < break_level
4️⃣ 弱反彈條件（ATR 模式）
abs(close - MA7) <= 0.5 * ATR
5️⃣ 上影線轉弱條件

high > min(MA7, MA25)

upper_shadow > 0.7 * ATR

volume < volume_mean * 1.1

6️⃣ 跌破 MA7 條件（替代訊號）

前 1~3 根曾在 MA7 上方

現在 close < MA7

volume > prev_volume

7️⃣ 進場價格與 K 棒限制

close < threshold
（threshold 由 ATR 與區間高低計算）

K棒實體大小：

body > 0.3 * ATR

body < 0.8 * ATR

close < open

volume > prev_volume * 1.0
（volume confirmation 有啟用）

🔴 出場條件（本次回測）
① ATR Trailing Exit（主要出場）

參數：

atr_trailing_profit = 1.5
atr_trailing_stop = 1.0

條件：

current_profit >= 1.5 * ATR / entry_price
且
回撤 >= 1.0 * ATR / entry_price
② MA25 Take Profit
close > MA25 * 1.01
③ MA25 Defense（風控）

參數：

defense_ma25_offset = 1.01
defense_max_loss = -1.5%
defense_min_age_candles = 10

條件：

close > MA25 * 1.01

current_profit <= -1.5%

持倉 ≥ 10 根K

🛑 動態 Stoploss
基本 SL
(high_rebound + 1.2*ATR) / entry_price - 1
最低 2%
時間縮緊
30 根K 後
SL <= 2%
Breakeven
若 profit >= 0.8%
SL 拉到 0%（保本）