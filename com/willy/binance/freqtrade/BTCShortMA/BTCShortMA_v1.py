from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

class BTCShortMA_v1(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '1h'
    can_short = True
    stoploss = -0.10
    minimal_roi = {"0": 100}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 計算基礎均線
        dataframe['ma25'] = ta.SMA(dataframe, timeperiod=25)
        dataframe['ma99'] = ta.SMA(dataframe, timeperiod=99)

        # 核心判斷：MA25 是否在 MA99 之上
        dataframe['ma25_above_ma99'] = (dataframe['ma25'] > dataframe['ma99'])

        # 計算過去 20 根 K 棒是否「全部」都符合 ma25 > ma99
        # shift(1) 是為了確保我們看的是「交叉發生前」的狀態
        # True/False rolling-all alternative compatible with pandas:
        # all True in the last 20 candles => rolling min equals 1.
        dataframe['pre_condition_stable'] = (
            dataframe['ma25_above_ma99'].shift(1).fillna(False).astype(int).rolling(window=20).min() == 1
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        進場條件：
        1. MA25 向下穿越 MA99
        2. 且在交叉發生前，MA25 已經在 MA99 上方維持了至少 20 根 K 棒
        """
        dataframe.loc[
            (
                    qtpylib.crossed_below(dataframe['ma25'], dataframe['ma99']) &
                    (dataframe['pre_condition_stable'] == True)
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        出場條件：收盤價大於 MA25
        """
        dataframe.loc[
            (
                    dataframe['close'] > dataframe['ma25']
            ),
            'exit_short'] = 1

        return dataframe
