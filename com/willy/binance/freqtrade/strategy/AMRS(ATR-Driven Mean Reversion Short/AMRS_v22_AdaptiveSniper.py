import logging
from datetime import datetime

import talib.abstract as ta
from freqtrade.strategy import IStrategy, merge_informative_pair
from pandas import DataFrame

logger = logging.getLogger(__name__)


class AMRS_v22_AdaptiveSniper(IStrategy):
    """
    AMRS v22 - 自適應狙擊手策略 (整合修正版)
    整合要點：
    1. 找回 V19 的強力進場過濾 (日線趨勢 + 2.2x 爆量 + RSI 空間)。
    2. 優化築底過濾器：使用 Rolling Min (底底高過濾)。
    3. 自適應 ATR 止損：根據波動度動態調整起始風險。
    4. 階梯式鎖利：0.5% 即啟動微利保護，大幅提升勝率。
    """
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 120

    # --- 交易性能參數 ---
    stoploss = -0.03  # 物理止損底線
    minimal_roi = {
        "0": 0.10,  # 10% 止盈
        "300": 0.05,  # 5小時後 5% 止盈
        "1440": 0.015  # 24小時後 1.5% 止盈 (確保高於手續費)
    }

    # 關閉內建追蹤止損，改由 custom_stoploss 階梯式精確控管
    trailing_stop = False

    def informative_pairs(self):
        return [(self.config['stake_currency'], '1d')]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 1. 日線指標 (1D) ---
        informative = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='1d')
        informative['ma25_day'] = ta.SMA(informative, timeperiod=25)
        informative['day_slope'] = informative['ma25_day'].diff(3)
        informative['adx'] = ta.ADX(informative)
        informative['minus_di'] = ta.MINUS_DI(informative)
        informative['plus_di'] = ta.PLUS_DI(informative)

        dataframe = merge_informative_pair(dataframe, informative, self.timeframe, '1d', ffill=True)

        # --- 2. 短線指標 (15m) ---
        dataframe['ma7'] = ta.SMA(dataframe, timeperiod=7)
        dataframe['ma25'] = ta.SMA(dataframe, timeperiod=25)
        dataframe['ma99'] = ta.SMA(dataframe, timeperiod=99)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        # 成交量指標
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=30).mean()

        # 價格行為輔助 (前一根高點)
        dataframe['prev_high'] = dataframe['high'].shift(1)

        # 築底偵測：最近 40 根 K 線的最低點
        dataframe['local_min'] = dataframe['close'].rolling(window=40).min()

        # 離場計數：連續站上 MA7
        dataframe['ma7_gt'] = (dataframe['close'] > dataframe['ma7']).astype(int)
        dataframe['streak_ma7'] = dataframe['ma7_gt'].rolling(window=10).sum()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        進場邏輯：強勢空頭狙擊 + 築底風險避讓
        """
        # 1. 日線大趨勢：空頭斜率 + 強勢 ADX (> 25)
        macro_filter = (
                (dataframe['day_slope_1d'] < 0) &
                (dataframe['adx_1d'] > 25) &
                (dataframe['minus_di_1d'] > dataframe['plus_di_1d'])
        )

        # 2. 短線動能：價格在均線下 + 2.2倍爆量 + RSI 尚有下跌空間 (> 35)
        momentum_filter = (
                (dataframe['close'] < dataframe['ma25']) &
                (dataframe['volume'] > dataframe['volume_mean'] * 2.2) &
                (dataframe['rsi'] > 35)
        )

        # 3. 築底過濾器 (底底高過濾)：
        # 如果現價已經比最近 10 小時的低點反彈超過 1%，代表可能在築底
        bottoming_risk = (dataframe['close'] > dataframe['local_min'] * 1.01)

        dataframe.loc[
            macro_filter & momentum_filter & (~bottoming_risk),
            ["enter_short", "enter_tag"]
        ] = (1, "v22_adaptive_sniper")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        技術指標硬性離場
        """
        dataframe.loc[
            (
                    (dataframe["streak_ma7"] >= 5) |  # 連續 5 根收在 MA7 上
                    (dataframe["close"] > dataframe["ma25"] * 1.003)  # 穿過 MA25 逃命門
            ),
            ["exit_short", "exit_tag"]
        ] = (1, "indicator_exit")
        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        自定義階梯止損：利潤越高，止損越緊
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]

        # 計算 ATR 動態初始止損 (1.5x ATR)
        atr_stop_pct = (last_candle['atr'] * 1.5) / last_candle['close']
        atr_stop_pct = max(min(atr_stop_pct, 0.025), 0.01)  # 限制在 1% ~ 2.5%

        # 1. 獲利 > 2.2%：鎖定大行情，給予 0.5% 的回撤空間
        if current_profit >= 0.022:
            return 0.005

        # 2. 獲利 > 1.2%：鎖定 0.6%
        if 0.012 <= current_profit < 0.022:
            return 0.006

        # 3. 獲利 > 0.5%：微利保護 (啟動保本，鎖住 0.2%)
        if 0.005 <= current_profit < 0.012:
            return 0.002

        # 尚未盈利前，使用 ATR 動態止損
        return -atr_stop_pct

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        """
        價格行為離場：外科醫生模式
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]
        prev_candle = dataframe.iloc[-2]

        # 如果已經有 0.2% 利潤且出現反轉信號 (收盤破前高)
        if current_profit > 0.002:
            if last_candle['close'] > prev_candle['high']:
                return "price_action_reversal"

        return None
