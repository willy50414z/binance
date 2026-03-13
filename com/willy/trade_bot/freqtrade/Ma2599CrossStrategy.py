from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

class Ma2599CrossStrategy(IStrategy):
    """
    Ma2599CrossStrategy
    做多策略: MA25 > MA99 黃金交叉
    做空策略: MA25 < MA99 死亡交叉
    停利策略: 獲利 > 15% (ROI)
    停損策略: 損失 > 20% (Stoploss)
    """

    INTERFACE_VERSION = 3

    # Timeframe
    timeframe = '15m'

    # 是否支援做空 (期貨模式必備)
    can_short = True

    # 停利策略: 獲利 > 15%
    # "0": 0.15 代表從 0 分鐘起算，只要獲利達 15% 就出場
    minimal_roi = {
        "0": 0.15
    }

    # 停損策略: 損失 > 20%
    stoploss = -0.20

    # 啟動時需要的 K 線數量 (為了計算 MA99)
    startup_candle_count: int = 99

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 計算 MA25 與 MA99
        dataframe['ma25'] = ta.SMA(dataframe, timeperiod=25)
        dataframe['ma99'] = ta.SMA(dataframe, timeperiod=99)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 初始化進場欄位
        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0

        # 做多：MA25 黃金交叉 MA99
        dataframe.loc[
            qtpylib.crossed_above(dataframe['ma25'], dataframe['ma99']),
            'enter_long'] = 1

        # 做空：MA25 死亡交叉 MA99
        dataframe.loc[
            qtpylib.crossed_below(dataframe['ma25'], dataframe['ma99']),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 初始化出場欄位
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0

        # 這裡由於使用者有設定強制的 ROI (15%) 與 Stoploss (20%)，
        # 如果您希望在「反向交叉」時也提前出場，可以取消下方註解：
        
        # 做多出場：MA25 跌破 MA99
        # dataframe.loc[
        #     qtpylib.crossed_below(dataframe['ma25'], dataframe['ma99']),
        #     'exit_long'] = 1

        # 做空出場：MA25 突破 MA99
        # dataframe.loc[
        #     qtpylib.crossed_above(dataframe['ma25'], dataframe['ma99']),
        #     'exit_short'] = 1

        return dataframe
