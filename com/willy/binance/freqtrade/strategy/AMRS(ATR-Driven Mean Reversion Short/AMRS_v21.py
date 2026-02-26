import logging
from datetime import datetime

import talib.abstract as ta
from freqtrade.strategy import IStrategy
from pandas import DataFrame

logger = logging.getLogger(__name__)


class AMRS_v21(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 120

    # --- 交易性能參數 ---
    # V20 使用動態止損，這裡設一個較寬的物理底線
    stoploss = -0.03

    # 稍微放寬 ROI，讓 ATR 追蹤止損來決定出場
    minimal_roi = {
        "0": 0.10,
        "300": 0.05,
        "1440": 0.01
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # (保持原有的 ma7, ma25, rsi, atr 計算)
        dataframe['ma7'] = ta.SMA(dataframe, timeperiod=7)
        dataframe['ma25'] = ta.SMA(dataframe, timeperiod=25)
        dataframe['ma99'] = ta.SMA(dataframe, timeperiod=99)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_mean'] = dataframe['atr'].rolling(window=100).mean()
        dataframe['ma25_max_100'] = dataframe['ma25'].rolling(window=100).max()
        dataframe['ma99_max_100'] = dataframe['ma99'].rolling(window=100).max()

        # 為了 exit_trend 增加連漲/連跌計數
        dataframe['ma7_gt_prev'] = (dataframe['close'] > dataframe['ma7']).astype(int)
        dataframe['streak_ma7'] = dataframe['ma7_gt_prev'].rolling(window=10).sum()

        dataframe['volume_mean'] = dataframe['volume'].rolling(window=30).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 原有的基礎條件 ---
        base_cond = (
                (dataframe['close'] < dataframe['ma7']) &
                (dataframe['ma7'] < dataframe['ma25'])
        )

        # --- 新增：築底過濾邏輯 ---
        # 1. 取得上一次進場時的價格 (假設 tag 為 v20_adaptive_entry)
        # 我們先標記所有符合基礎條件的點，然後看它的前一個點
        if 'enter_short' in dataframe.columns:
            entry_mask = dataframe['enter_short'] == 1
        else:
            entry_mask = dataframe['close'] < float('-inf')
        last_entry_price = dataframe['close'].where(entry_mask).ffill().shift(1)

        # 2. 定義「築底風險」：現價 > 上次進場價 且 MA25 最大值 < MA99 最大值 (長期空頭壓力減弱)
        # 這裡的 window 可以根據你的觀察調整，例如 40 根 K 線 (約 10 小時)
        max_ma25 = dataframe['ma25'].rolling(window=40).max()
        max_ma99 = dataframe['ma99'].rolling(window=40).max()

        bottoming_risk = (
                (dataframe['close'] > last_entry_price) &
                (max_ma25 < max_ma99)
        )

        # --- 最終進場組合 ---
        dataframe.loc[
            base_cond & (~bottoming_risk),  # 使用波浪號 ~ 表示「非」築底風險
            ["enter_short", "enter_tag"]
        ] = (1, "v20_shield_entry")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        硬性指標出場邏輯 (作為 custom_exit 的第一道過濾)
        """
        dataframe.loc[
            (
                # 1. 趨勢徹底反轉：價格連續 5 根 K 線站穩在 MA7 之上 (對於 Short 來說是危險)
                    (dataframe["streak_ma7"] >= 5) |

                    # 2. 乖離率過高：價格反彈超過 MA25 的 0.5% (強勢反彈預警)
                    (dataframe["close"] > dataframe["ma25"] * 1.005)
            ),
            ["exit_short", "exit_tag"]
        ] = (1, "v20_indicator_exit")

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]

        # 計算 ATR 止損距離 (約為 1.5 倍 ATR)
        # 換算成百分比
        atr_stop_pct = (last_candle['atr'] * 1.5) / last_candle['close']
        atr_stop_pct = max(min(atr_stop_pct, 0.025), 0.01)  # 限制在 1%~2.5% 之間

        # 1. 獲利超過 0.5%：立刻大幅縮減風險 (Move to partial break-even)
        if 0.005 <= current_profit < 0.012:
            return 0.002  # 鎖住 0.2% 獲利

        # 2. 獲利超過 1.2%：鎖住 0.6%
        if 0.012 <= current_profit < 0.022:
            return 0.006

        # 3. 大行情追蹤：獲利超過 2.2% 啟動 0.5% 寬度的追蹤止損
        if current_profit >= 0.022:
            return 0.005

        # 初始動態止損
        return -atr_stop_pct

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]
        prev_candle = dataframe.iloc[-2]

        # --- V20 價格行為離場 ---
        # 只要當前收盤高於前一根 K 線高點，代表短期反彈確立
        if current_profit > 0.002:  # 只要有微利
            if last_candle['close'] > prev_candle['high']:
                return "v20_pa_reversal"

        # 安全防護：價格重回 MA25 上方
        if last_candle['close'] > last_candle['ma25'] * 1.003:
            return "ma25_protection"

        return None
