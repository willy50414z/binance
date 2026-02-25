import logging
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy, merge_informative_pair
from pandas import DataFrame
import numpy as np

logger = logging.getLogger(__name__)


class AMRS_v14_EnhancedStrategy(IStrategy):
    """
    AMRS v11 優化版
    優化重點：提高平均單筆報酬、降低摩擦成本、過濾過度延伸的進場
    """
    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 120

    # --- 交易性能參數優化 ---
    minimal_roi = {
        "0": 0.10,  # 10% 強制止盈
        "240": 0.05,  # 持倉超過 4 小時後，5% 止盈
        "720": 0.02  # 持倉超過 12 小時後，2% 止盈 (確保長線不虧手續費)
    }

    stoploss = -0.04  # 稍微收緊原始止損至 4%

    # 追蹤止損優化：降低觸發門檻 (Offset)，讓獲利單更快進入保護狀態
    trailing_stop = True
    trailing_stop_positive = 0.002  # 追蹤間距 0.2%
    trailing_stop_positive_offset = 0.007  # 獲利達 0.7% 即開啟追蹤 (原為 1%)
    trailing_only_offset_is_reached = True

    # 策略內部參數
    ma7_len = 7
    ma25_len = 25
    ma99_len = 99
    exit_confirm_candles = 5  # 增加確認根數 (從 3 改為 5)，減少頻繁進出

    def informative_pairs(self):
        return [(self.config['stake_currency'], '1d')]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 1. 日線指標 (1D) --- 確保大趨勢方向
        informative = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='1d')
        informative['ma25_day'] = ta.SMA(informative, timeperiod=25)
        informative['day_slope'] = informative['ma25_day'].diff(3)
        informative['adx'] = ta.ADX(informative)
        informative['plus_di'] = ta.PLUS_DI(informative)
        informative['minus_di'] = ta.MINUS_DI(informative)

        dataframe = merge_informative_pair(dataframe, informative, self.timeframe, '1d', ffill=True)

        # --- 2. 短線指標 (15m) ---
        dataframe['ma7'] = ta.SMA(dataframe, timeperiod=self.ma7_len)
        dataframe['ma25'] = ta.SMA(dataframe, timeperiod=self.ma25_len)
        dataframe['ma99'] = ta.SMA(dataframe, timeperiod=self.ma99_len)

        # 乖離率過濾 (Distance from MA) - 防止追漲殺跌
        dataframe['ma25_dist'] = (dataframe['ma25'] - dataframe['close']) / dataframe['ma25']

        # 趨勢斜率
        dataframe['ma25_slope'] = dataframe['ma25'].diff(3)

        # 成交量過濾
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=30).mean()

        # 離場計數器 (MA7 突破確認)
        dataframe['ma7_cross_above'] = (dataframe['close'] > dataframe['ma7']).astype(int)
        dataframe['streak_ma7'] = dataframe['ma7_cross_above'].rolling(window=self.exit_confirm_candles).sum()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        進場邏輯優化：增加乖離率限制
        """
        # 基礎結構條件
        base_filter = (
                (dataframe['ma25_slope'] < 0) &
                (dataframe['close'] < dataframe['ma99']) &
                (dataframe['volume'] > dataframe['volume_mean'] * 1.5)  # 稍微放寬成交量，但仍需爆量
        )

        # 核心過濾：防止「過度延伸」
        # 如果當前價格已經跌離 MA25 超過 1.5%，代表短線可能過熱，不宜進場追空
        extension_filter = (dataframe['ma25_dist'] < 0.015)

        # 大週期過濾 (1D)
        macro_filter = (
                (dataframe['day_slope_1d'] <= 0) &
                (dataframe['adx_1d'] > 20) &  # 提高 ADX 門檻，確保有明確趨勢
                (dataframe['minus_di_1d'] > dataframe['plus_di_1d'])
        )

        dataframe.loc[
            base_filter & extension_filter & macro_filter,
            ["enter_short", "enter_tag"]
        ] = (1, "v11_optimized_entry")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        離場邏輯優化：減少被震盪誤殺
        """
        # 條件 1: MA7 持續突破確認 (由 3 根改為 5 根)
        # 條件 2: 價格大幅偏離 MA25 (硬性保護)
        dataframe.loc[
            (dataframe["streak_ma7"] >= self.exit_confirm_candles) |
            (dataframe["close"] > (dataframe["ma25"] * 1.002)),  # 稍微放寬容忍度
            "exit_short"
        ] = 1

        return dataframe

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        """
        自定義離場邏輯：確保覆蓋摩擦成本
        """
        # 如果當前利潤連手續費都跑不贏 (例如 < 0.15%)，除非觸發止損，否則儘量不主動離場
        if current_profit < 0.0015 and trade.calc_profit_ratio(current_rate) > -0.02:
            return None

        # 快速止盈保護：如果短時間內大幅獲利，提前鎖定
        if current_profit > 0.025:
            return "v11_quick_profit_shield"

        return None
