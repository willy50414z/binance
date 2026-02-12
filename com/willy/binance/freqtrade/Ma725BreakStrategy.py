import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime, timedelta
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

class Ma725BreakStrategy(IStrategy):
    """
    Ma725BreakStrategy ported from custom Python implementation.
    
    Original Logic:
    1. Entry: MA7 crosses MA25 after a long trend (20 periods) in the opposite direction.
    2. Filters: RSI, ATR, Time Filter (22:00-01:00 UTC excluded).
    3. Exit: MA7 crosses back.
    4. Stoploss: Mainstream Trailing Stop (User requested).
    """

    INTERFACE_VERSION = 3

    # Minimal ROI designed for the strategy.
    # We rely on trend following (exit on signal) and trailing stop.
    minimal_roi = {
        "0": 100  # Let the strategy decide exit or trailing stop hit
    }

    # Mainstream Stoploss Strategy (User Request)
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # Timeframe
    timeframe = '15m'

    # Strategy parameters
    # RSI filter: >= 60 for Long, <= 40 for Short (implied symmetry)? 
    # Original code only had 'fail in rsi fall' (ma7>ma25 and rsi<60).
    buy_rsi = IntParameter(60, 90, default=60, space='buy')
    
    can_short = True
    
    # Run "populate_indicators" only for new candle
    process_only_new_candles = True

    # These values can be overridden in the config file
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Startup candle count necessary for this strategy
    startup_candle_count: int = 100

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # MA7 and MA25
        dataframe['ma7'] = ta.SMA(dataframe, timeperiod=7)
        dataframe['ma25'] = ta.SMA(dataframe, timeperiod=25)

        # RSI and ATR
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_mean'] = dataframe['atr'].rolling(window=100).mean()

        # MA25 Slope (Keep Grow / Keep Fall)
        dataframe['ma25_diff'] = dataframe['ma25'].diff()
        dataframe['is_ma25_keep_grow'] = dataframe['ma25_diff'] > 0
        dataframe['is_ma25_keep_fall'] = dataframe['ma25_diff'] < 0
        
        # Trend State
        # Long Trend: MA7 > MA25
        # Short Trend: MA7 < MA25
        dataframe['ma7_gt_ma25'] = (dataframe['ma7'] > dataframe['ma25']).astype(int)
        dataframe['ma7_lt_ma25'] = (dataframe['ma7'] < dataframe['ma25']).astype(int)

        # Calculate duration of the trend
        # We need to know if the trend held for 20 periods
        dataframe['trend_long_streak'] = dataframe['ma7_gt_ma25'].rolling(window=20).sum()
        dataframe['trend_short_streak'] = dataframe['ma7_lt_ma25'].rolling(window=20).sum()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on trade_if_cross_ma logic:
        1. Confirm MA7/MA25 maintained same direction for > 20 periods.
        2. If trend changes (Cross), and Tech Filters passed -> Entry.
        
        Also implements 'Fake Break' logic which bypasses filters.
        """
        
        # Initialize columns
        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0

        # Calculate Crossovers
        dataframe['cross_above'] = qtpylib.crossed_above(dataframe['ma7'], dataframe['ma25'])
        dataframe['cross_below'] = qtpylib.crossed_below(dataframe['ma7'], dataframe['ma25'])
        
        # Calculate "Recent Crossovers" for Fake Break detection (look back 5 candles)
        # We shift by 1 to check if *previous* 5 candles had a crossover
        dataframe['recent_cross_below'] = dataframe['cross_below'].rolling(window=5).max().shift(1)
        dataframe['recent_cross_above'] = dataframe['cross_above'].rolling(window=5).max().shift(1)

        # 1. Entry Long conditions
        
        # A. Standard Trend Break
        enter_long_standard = (
            dataframe['cross_above'] &
            (dataframe['trend_short_streak'].shift(1) == 20) & 
            (dataframe['is_ma25_keep_fall'] == False) &
            (dataframe['rsi'] >= 60) &
            (dataframe['atr'] >= (dataframe['atr_mean'] * 0.8)) &
            (dataframe['volume'] > 0)
        )
        
        # B. Fake Break (Re-entry)
        # Logic: Current Cross Above + Recent Cross Below (approx < 5 candles ago)
        # Original code does NOT check RSI/ATR for fake break.
        enter_long_fake_break = (
            dataframe['cross_above'] &
            (dataframe['recent_cross_below'] > 0) &
            (dataframe['volume'] > 0)
        )

        dataframe.loc[
            (enter_long_standard | enter_long_fake_break),
            'enter_long'] = 1

        # 2. Entry Short conditions
        
        # A. Standard Trend Break
        enter_short_standard = (
            dataframe['cross_below'] &
            (dataframe['trend_long_streak'].shift(1) == 20) &
            (dataframe['is_ma25_keep_grow'] == False) &
            (dataframe['atr'] >= (dataframe['atr_mean'] * 0.8)) &
            (dataframe['volume'] > 0)
        )
        
        # B. Fake Break (Re-entry)
        # Logic: Current Cross Below + Recent Cross Above
        enter_short_fake_break = (
            dataframe['cross_below'] &
            (dataframe['recent_cross_above'] > 0) &
            (dataframe['volume'] > 0)
        )

        dataframe.loc[
            (enter_short_standard | enter_short_fake_break),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on trade_if_cross_ma logic:
        The strategy reverses when the signal reverses.
        """
        
        # Initialize
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0

        # Exit Long
        dataframe.loc[
            (
                # Signal Reverse: MA7 < MA25
                (dataframe['ma7'] < dataframe['ma25']) &
                (dataframe['volume'] > 0)
            ),
            'exit_long'] = 1

        # Exit Short
        dataframe.loc[
            (
                # Signal Reverse: MA7 > MA25
                (dataframe['ma7'] > dataframe['ma25']) &
                (dataframe['volume'] > 0)
            ),
            'exit_short'] = 1

        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: str,
                            side: str, **kwargs) -> bool:
        """
        Checks additional filters: Time Filter and Cool Down.
        """
        
        # 1. Time Filter (22:00 - 01:00 UTC)
        # Original: 22, 23, 0 forbidden
        # Note: current_time is usually UTC in Freqtrade
        if current_time.hour in [22, 23, 0]:
            return False

        # 2. Cool Down Period (Simplified)
        # If the last closed trade was a loss, we might want to skip this trade.
        trades = Trade.get_trades_proxy(pair=pair, is_open=False)
        if trades:
            last_trade = trades[-1]
            # If last trade was a loss
            if last_trade.close_profit < 0:
                # Check how recently it closed. 
                # Original logic: 2 consecutive losses -> 96 periods (24 hours). 1 loss -> 1 period?
                # Let's enforce a 1 hour cool down for any loss for safety in this simulation.
                if (current_time - last_trade.close_date_utc).total_seconds() < 3600:
                    return False

        return True
