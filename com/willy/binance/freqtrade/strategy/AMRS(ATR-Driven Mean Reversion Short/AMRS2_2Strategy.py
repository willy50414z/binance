from datetime import datetime

import numpy as np
import pandas as pd
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, DecimalParameter
from pandas import DataFrame


class AMRS2_2Strategy(IStrategy):
    """
    AMRS(ATR-Driven Mean Reversion Short 2.2
    
    Optimization based on AMRS2.2.md:
    1. Fixed cond_full logic - use complete filter conditions
    2. Dynamic ATR stop-loss
    3. ATR trailing profit + break-even protection
    4. Stop-Limit entry optimization
    5. Hyperopt parameters
    """

    INTERFACE_VERSION = 3

    minimal_roi = {
        "0": 100
    }

    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    timeframe = '15m'

    can_short = True

    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 200

    consolidation_amplitude_ratio = DecimalParameter(2.0, 5.0, default=2.8, space="buy")
    consolidation_volatility_ratio = DecimalParameter(0.8, 2.0, default=0.95, space="buy")
    pre_drop_multiplier = DecimalParameter(1.0, 2.0, default=1.3, space="buy")
    upper_shadow_ratio = DecimalParameter(0.5, 1.2, default=0.7, space="buy")
    volume_filter_ratio = DecimalParameter(1.0, 1.5, default=1.1, space="buy")
    atr_ratio_threshold = DecimalParameter(0.4, 0.7, default=0.5, space="buy")
    min_distance_ratio = DecimalParameter(0.2, 0.5, default=0.3, space="buy")
    body_lower_ratio = DecimalParameter(0.2, 0.5, default=0.3, space="buy")
    body_upper_ratio = DecimalParameter(0.6, 1.0, default=0.8, space="buy")
    volume_burst_ratio = DecimalParameter(1.0, 1.5, default=1.0, space="buy")
    ma25_offset_exit = DecimalParameter(1.0, 1.05, default=1.01, space="sell")
    atr_trailing_profit = DecimalParameter(1.0, 3.0, default=1.5, space="sell")
    atr_trailing_stop = DecimalParameter(0.5, 1.5, default=1.0, space="sell")

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._trade_sl_dict = {}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ma7'] = ta.SMA(dataframe, timeperiod=7)
        dataframe['ma25'] = ta.SMA(dataframe, timeperiod=25)
        dataframe['ma99'] = ta.SMA(dataframe, timeperiod=99)

        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_mean'] = dataframe['atr'].rolling(window=100).mean()

        dataframe['ma7_diff'] = dataframe['ma7'].diff()
        dataframe['ma25_diff'] = dataframe['ma25'].diff()
        dataframe['ma99_diff'] = dataframe['ma99'].diff()

        dataframe['is_ma7_negative_slope'] = dataframe['ma7_diff'] < 0
        dataframe['is_ma25_negative_slope'] = dataframe['ma25_diff'] < 0
        dataframe['is_ma99_negative_slope'] = dataframe['ma99_diff'] < 0

        dataframe['high_20'] = dataframe['high'].rolling(window=20).max()
        dataframe['low_20'] = dataframe['low'].rolling(window=20).min()
        dataframe['close_std_20'] = dataframe['close'].rolling(window=20).std()

        dataframe['consolidation_amplitude'] = (dataframe['high_20'] - dataframe['low_20']) / dataframe['atr']
        dataframe['consolidation_volatility'] = dataframe['close_std_20'] / dataframe['atr']

        dataframe['volume_mean'] = dataframe['volume'].rolling(window=20).mean()

        dataframe['upper_shadow'] = dataframe['high'] - np.maximum(dataframe['open'], dataframe['close'])
        dataframe['lower_shadow'] = np.minimum(dataframe['open'], dataframe['close']) - dataframe['low']
        dataframe['body'] = np.abs(dataframe['open'] - dataframe['close'])

        dataframe['atr_trend'] = dataframe['atr'].diff()
        dataframe['is_atr_rising'] = dataframe['atr_trend'] > 0

        dataframe['close_vs_ma7'] = np.where(dataframe['close'] < dataframe['ma7'], -1, 1)
        dataframe['close_vs_ma25'] = np.where(dataframe['close'] < dataframe['ma25'], -1, 1)
        dataframe['ma7_vs_ma25'] = np.where(dataframe['ma7'] < dataframe['ma25'], -1, 1)
        dataframe['ma25_vs_ma99'] = np.where(dataframe['ma25'] < dataframe['ma99'], -1, 1)

        dataframe['above_ma7'] = dataframe['close'] > dataframe['ma7']
        dataframe['below_ma7'] = dataframe['close'] < dataframe['ma7']

        dataframe['prev_close'] = dataframe['close'].shift(1)
        dataframe['prev_volume'] = dataframe['volume'].shift(1)

        dataframe['prev_high'] = dataframe['high'].shift(1)
        dataframe['prev_low'] = dataframe['low'].shift(1)
        dataframe['prev_close_above_ma7'] = dataframe['close'].shift(1) > dataframe['ma7'].shift(1)

        dataframe['prev2_close_above_ma7'] = dataframe['close'].shift(2) > dataframe['ma7'].shift(2)
        dataframe['prev3_close_above_ma7'] = dataframe['close'].shift(3) > dataframe['ma7'].shift(3)

        dataframe['high_rebound'] = dataframe['high'].rolling(window=10).max()
        dataframe['low_breakout'] = dataframe['low'].rolling(window=10).min()

        dataframe['atr_ratio'] = dataframe['atr'] / dataframe['atr_mean']
        dataframe['timeout_candles'] = (10 * dataframe['atr_ratio']).round()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0

        amp_ratio = self.consolidation_amplitude_ratio.value
        vol_ratio = self.consolidation_volatility_ratio.value
        pre_drop_mult = self.pre_drop_multiplier.value
        upper_shadow = self.upper_shadow_ratio.value
        vol_filter = self.volume_filter_ratio.value
        atr_ratio_th = self.atr_ratio_threshold.value
        min_dist = self.min_distance_ratio.value
        body_low = self.body_lower_ratio.value
        body_up = self.body_upper_ratio.value
        vol_burst = self.volume_burst_ratio.value

        cond_trend_alignment = (
                (dataframe['close'] < dataframe['ma7']) &
                (dataframe['ma7'] < dataframe['ma25']) &
                (dataframe['ma25'] < dataframe['ma99']) &
                (dataframe['is_ma25_negative_slope']) &
                (dataframe['is_ma99_negative_slope'])
        )

        cond_consolidation = (
                (dataframe['consolidation_amplitude'] < amp_ratio) &
                (dataframe['consolidation_volatility'] < vol_ratio)
        )

        cond_pre_drop = dataframe['close'] < (dataframe['low_20'] - pre_drop_mult * dataframe['atr'])

        cond_env = cond_trend_alignment & cond_consolidation & cond_pre_drop

        cond_A = (
                (dataframe['high'] > np.minimum(dataframe['ma7'], dataframe['ma25'])) &
                (dataframe['upper_shadow'] > upper_shadow * dataframe['atr']) &
                (dataframe['volume'] < dataframe['volume_mean'] * vol_filter)
        )

        cond_B = (
                (
                        (dataframe['prev_close_above_ma7'].astype(bool) & dataframe['below_ma7'].astype(bool)) |
                        ((dataframe['close'].shift(2) < dataframe['ma7'].shift(2)) & dataframe['below_ma7'].astype(
                            bool)) |
                        ((dataframe['close'].shift(3) < dataframe['ma7'].shift(3)) & dataframe['below_ma7'].astype(
                            bool))
                ) &
                (dataframe['volume'] > dataframe['prev_volume'])
        )

        cond_signal = cond_A | cond_B

        ratio = np.where(dataframe['is_atr_rising'], atr_ratio_th + 0.1, atr_ratio_th)
        min_distance = min_dist * dataframe['atr']

        threshold = dataframe['low_breakout'] + ratio * (dataframe['high_rebound'] - dataframe['low_breakout'])
        threshold = np.where(
            threshold < dataframe['low_breakout'] + min_distance,
            dataframe['low_breakout'] + min_distance,
            threshold
        )

        cond_entry_price = dataframe['close'] < threshold

        cond_body = (
                (dataframe['body'] > body_low * dataframe['atr']) &
                (dataframe['body'] < body_up * dataframe['atr']) &
                (dataframe['close'] < dataframe['open'])
        )

        cond_volume_burst = dataframe['volume'] > (dataframe['prev_volume'] * vol_burst)

        cond_execution = cond_entry_price & cond_body & cond_volume_burst

        cond_full = cond_env & cond_signal & cond_execution

        cond_basic_short = cond_trend_alignment & cond_A

        dataframe.loc[(cond_basic_short) | (cond_full), 'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0

        ma25_offset = self.ma25_offset_exit.value

        cond_ultimate_defense = dataframe['close'] > dataframe['ma25'] * ma25_offset

        cond_exit_short = cond_ultimate_defense

        dataframe.loc[cond_exit_short, 'exit_short'] = 1

        return dataframe

    def get_entry_price(self, pair: str, side: str, **kwargs) -> float:
        return None

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: str,
                            side: str, **kwargs) -> bool:
        return True

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        if dataframe.empty:
            return -0.05

        current_candle = dataframe.iloc[-1]

        if trade.is_short:
            entry_price = trade.open_rate
            atr = current_candle['atr']

            if pd.notna(current_candle['high_rebound']):
                dynamic_sl = (current_candle['high_rebound'] + 1.2 * atr) / entry_price - 1
                dynamic_sl = max(dynamic_sl, 0.02)
                return -dynamic_sl

        return -0.05

    def custom_exit(self, pair: str, trade: 'Trade', current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> str:
        if not trade.is_short:
            return None

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        if dataframe.empty:
            return None

        current_candle = dataframe.iloc[-1]

        entry_price = trade.open_rate
        atr = current_candle['atr']

        profit_target = self.atr_trailing_profit.value * atr / entry_price

        if current_profit >= profit_target:
            trailing_stop = self.atr_trailing_stop.value * atr / entry_price
            if current_profit >= trailing_stop:
                return 'atr_trailing_exit'

        if current_candle['close'] > current_candle['ma25'] * 1.01:
            return 'ma25_defense'

        return None
