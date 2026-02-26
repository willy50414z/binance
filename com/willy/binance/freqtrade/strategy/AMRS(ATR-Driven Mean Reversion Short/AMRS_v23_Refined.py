import logging
from datetime import datetime

import talib.abstract as ta
from freqtrade.strategy import IStrategy, merge_informative_pair
from pandas import DataFrame

logger = logging.getLogger(__name__)


class AMRS_v23_Refined(IStrategy):
    """
    AMRS v23 - 邏輯收斂與精簡版 (Short Only)
    優化重點：
    1. 簡化離場邏輯：移除敏感的 MA7 交叉，回歸 MA25 趨勢底線。
    2. 強化價格行為離場：以 Price Action 作為獲利守護的核心。
    3. 參數化配置：提高策略維護性與靈活性。
    """
    INTERFACE_VERSION = 3
    timeframe = '15m'
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 120

    # --- 策略核心參數 (收斂) ---
    stoploss = -0.03
    minimal_roi = {'0': 0.10, '300': 0.05, '1440': 0.015}

    # 參數化配置
    bottom_threshold = 0.01  # 築底過濾門檻 (1%)
    volume_multiplier = 2.2  # 爆量倍率
    adx_threshold = 25  # 強勢趨勢門檻

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
        dataframe['ma25'] = ta.SMA(dataframe, timeperiod=25)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        # 成交量平均
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=30).mean()

        # 築底偵測：最近 40 根 K 線的最低點
        dataframe['local_min'] = dataframe['close'].rolling(window=40).min()

        # 前一根高點 (PA 離場用)
        dataframe['prev_high'] = dataframe['high'].shift(1)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. 大趨勢確認
        macro_trend = (
                (dataframe['day_slope_1d'] < 0) &
                (dataframe['adx_1d'] > self.adx_threshold) &
                (dataframe['minus_di_1d'] > dataframe['plus_di_1d'])
        )

        # 2. 短線下殺確認
        momentum_filter = (
                (dataframe['close'] < dataframe['ma25']) &
                (dataframe['volume'] > dataframe['volume_mean'] * self.volume_multiplier) &
                (dataframe['rsi'] > 35)
        )

        # 3. 築底避讓
        bottoming_risk = (dataframe['close'] > dataframe['local_min'] * (1 + self.bottom_threshold))

        dataframe.loc[macro_trend & momentum_filter & (~bottoming_risk), ['enter_short', 'enter_tag']] = (1,
                                                                                                          'v23_refined_sniper')
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 簡化指標離場：回歸趨勢線 MA25
        dataframe.loc[(dataframe['close'] > dataframe['ma25']), ['exit_short', 'exit_tag']] = (1, 'trend_reversal_exit')
        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float,
                        current_profit: float, **kwargs) -> float:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]

        atr_stop_pct = (last_candle['atr'] * 1.5) / last_candle['close']
        atr_stop_pct = max(min(atr_stop_pct, 0.025), 0.01)

        # 階梯鎖利
        if current_profit >= 0.022: return 0.005
        if 0.012 <= current_profit < 0.022: return 0.006
        if 0.005 <= current_profit < 0.012: return 0.002
        return -atr_stop_pct

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]

        # 核心：Price Action 離場 (外科醫生模式)
        if current_profit > 0.002:
            if last_candle['close'] > last_candle['prev_high']:
                return 'pa_reversal_exit'
        return None
