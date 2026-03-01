import logging
from datetime import datetime

import talib.abstract as ta
from freqtrade.strategy import IStrategy, merge_informative_pair
from pandas import DataFrame

logger = logging.getLogger(__name__)


class AMRS_v17(IStrategy):
    """
    AMRS v12 Sniper Strategy
    專門解決低獲利率與高交易成本問題。
    - 減少交易頻率
    - 提高每筆獲利期望值
    - 加入 RSI 與 強制利潤門檻
    """
    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 120

    # --- 交易性能參數 (嚴格化) ---
    minimal_roi = {
        "0": 0.15,  # 15% 止盈
        "300": 0.05,  # 5小時後 5% 止盈
        "1440": 0.01  # 持倉一天後，只要有 1% 就出清
    }

    # 止損稍微收緊，止損要快，獲利要拿穩
    stoploss = -0.03

    # 追蹤止損：給予更多「呼吸」空間
    trailing_stop = True
    trailing_stop_positive = 0.003  # 增加到 0.3%，避免噪音觸發
    trailing_stop_positive_offset = 0.012  # 提高門檻到 1.2%，讓子彈先飛一會兒
    trailing_only_offset_is_reached = True

    def informative_pairs(self):
        return [(self.config['stake_currency'], '1d')]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. 日線指標 (1D)
        informative = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='1d')
        informative['ma25_day'] = ta.SMA(informative, timeperiod=25)
        informative['day_slope'] = informative['ma25_day'].diff(3)
        informative['adx'] = ta.ADX(informative)
        informative['minus_di'] = ta.MINUS_DI(informative)
        informative['plus_di'] = ta.PLUS_DI(informative)

        dataframe = merge_informative_pair(dataframe, informative, self.timeframe, '1d', ffill=True)

        # 2. 短線指標 (15m)
        dataframe['ma7'] = ta.SMA(dataframe, timeperiod=7)
        dataframe['ma25'] = ta.SMA(dataframe, timeperiod=25)
        dataframe['ma99'] = ta.SMA(dataframe, timeperiod=99)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        # 乖離率與成交量
        dataframe['ma25_dist'] = (dataframe['ma25'] - dataframe['close']) / dataframe['ma25']
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=30).mean()

        # 離場確認邏輯
        dataframe['ma7_cross_above'] = (dataframe['close'] > dataframe['ma7']).astype(int)
        dataframe['streak_ma7'] = dataframe['ma7_cross_above'].rolling(window=5).sum()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        進場邏輯：狙擊手模式
        """
        # 1. 強度過濾：日線必須有強烈下降趨勢 (ADX > 25)
        macro_trend = (
                (dataframe['day_slope_1d'] < 0) &
                (dataframe['adx_1d'] > 25) &
                (dataframe['minus_di_1d'] > dataframe['plus_di_1d'])
        )

        # 2. 爆量條件：成交量必須是平均的 2.5 倍以上 (高品質訊號)
        volume_spike = (dataframe['volume'] > dataframe['volume_mean'] * 2.5)

        # 3. 空間過濾：RSI 必須高於 35，防止空在「地板」上
        space_filter = (dataframe['rsi'] > 35)

        # 4. 價格結構
        price_structure = (
                (dataframe['close'] < dataframe['ma99']) &
                (dataframe['close'] < dataframe['ma25'])
        )

        dataframe.loc[
            macro_trend & volume_spike & space_filter & price_structure,
            ["enter_short", "enter_tag"]
        ] = (1, "v12_sniper_entry")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 技術指標離場：MA7 持續突破或價格偏離
        dataframe.loc[
            (dataframe["streak_ma7"] >= 5) |
            (dataframe["close"] > dataframe["ma25"] * 1.005),
            "exit_short"
        ] = 1
        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        動態止損邏輯：利潤越高，止損越緊，但給予初期足夠空間
        """
        # 1. 獲利超過 2.5%：鎖定利潤，給予 0.2% 的回撤空間
        if current_profit > 0.025:
            return 0.002

        # 2. 獲利超過 1.2%：給予 0.5% 的空間 (避免 15m 噪音)
        if current_profit > 0.012:
            return 0.005

        # 3. 獲利超過 0.6%：移動到保本價格 (0.1% 利潤)
        if current_profit > 0.006:
            return 0.001

        # 4. 其他情況使用原始止損 (-3%)
        return self.stoploss

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]

        # --- V14 強力過濾 ---
        # 如果趨勢極強 (ADX > 30)，忽略微小的 MA7 反轉離場訊號
        if last_candle['adx_1d'] > 30 and current_profit > 0:
            if last_candle['close'] < last_candle['ma25']:  # 除非跌破 MA25 才走
                return "strong_trend_exit"
            return None

        # 原有的摩擦成本保護 (0.3% 以下不走)
        trade_duration = (current_time - trade.open_date_utc).total_seconds() / 60
        if current_profit < 0.003 and trade_duration < 360:
            return None

        return None
