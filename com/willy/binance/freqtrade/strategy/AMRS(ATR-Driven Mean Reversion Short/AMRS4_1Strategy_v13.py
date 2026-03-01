import logging
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy, merge_informative_pair
from pandas import DataFrame
import numpy as np

logger = logging.getLogger(__name__)


class AMRS4_1Strategy_v13(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 120

    # --- 參數調整：對抗 0.04% 手續費 ---
    minimal_roi = {"0": 10.0}
    stoploss = -0.05

    trailing_stop = True
    trailing_stop_positive = 0.003  # 0.3% 就啟動跟蹤
    trailing_stop_positive_offset = 0.008  # 獲利 0.8% 時觸發
    trailing_only_offset_is_reached = True

    def informative_pairs(self):
        return [(self.config['stake_currency'], '1d')]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 日線濾網 (維持 v10 最佳組合)
        informative = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='1d')
        informative['ma25_day'] = ta.SMA(informative, timeperiod=25)
        informative['day_slope'] = informative['ma25_day'].diff()
        informative['adx'] = ta.ADX(informative, timeperiod=14)
        informative['minus_di'] = ta.MINUS_DI(informative, timeperiod=14)
        informative['plus_di'] = ta.PLUS_DI(informative, timeperiod=14)
        dataframe = merge_informative_pair(dataframe, informative, self.timeframe, '1d', ffill=True)

        # 15m 指標
        dataframe["ma7"] = ta.SMA(dataframe, timeperiod=7)
        dataframe["ma25"] = ta.SMA(dataframe, timeperiod=25)
        dataframe["ma99"] = ta.SMA(dataframe, timeperiod=99)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # 輔助判定
        dataframe['is_bull'] = dataframe['close'] > dataframe['open']
        dataframe['close_gt_ma7'] = dataframe['close'] > dataframe['ma7']
        # 連續 2 根陽線且站上 MA7 (比 v12 的 4 根更敏捷)
        dataframe['bull_exit_signal'] = (dataframe['is_bull']) & (dataframe['close_gt_ma7'])
        dataframe['streak_bull'] = self._streak_true(dataframe['bull_exit_signal'])

        # 形態
        dataframe['body_min'] = np.minimum(dataframe['open'], dataframe['close'])
        dataframe['ten_candle_low'] = dataframe['body_min'].shift(1).rolling(window=10).min()
        dataframe['body_size'] = dataframe['open'] - dataframe['close']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        entry_condition = (
                (dataframe["close"] < dataframe["ma99"]) &
                (dataframe["ma7"] < dataframe["ma25"]) &
                (dataframe["close"] < dataframe["ten_candle_low"]) &
                (dataframe["body_size"] >= (dataframe['atr'] * 1.4)) &
                (dataframe['day_slope_1d'] <= 0) &
                (dataframe['adx_1d'] > 18) &
                (dataframe['minus_di_1d'] > dataframe['plus_di_1d'])
        )
        dataframe.loc[entry_condition, "enter_short"] = 1
        dataframe.loc[entry_condition, "enter_tag"] = "v13_profit_guard"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 只要連續兩根強勢反彈就走，保護利潤
        dataframe.loc[dataframe["streak_bull"] >= 2, "exit_short"] = 1
        dataframe.loc[dataframe["streak_bull"] >= 2, "exit_tag"] = "quick_reversal_exit"

        # MA25 強制止損線
        dataframe.loc[dataframe["close"] > dataframe["ma25"], "exit_short"] = 1
        dataframe.loc[dataframe["close"] > dataframe["ma25"], "exit_tag"] = "ma25_hard_exit"
        return dataframe

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        # 【核心：0.04% 手續費保險】
        # 只要獲利超過 0.6%，且現在有反彈跡象 (收盤 > MA7)，立刻落袋
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        if current_profit > 0.006:  # 獲利 > 0.6%
            if last_candle['close'] > last_candle['ma7']:
                return "lock_profit_06"

        # 獲利超過 1.2% 後，只要不是強勢大黑 K 就走
        if current_profit > 0.012:
            if last_candle['close'] > last_candle['open']:  # 陽 K 就跑
                return "big_win_exit"

        return None

    @staticmethod
    def _streak_true(cond: pd.Series) -> pd.Series:
        cond = cond.fillna(False).astype(bool)
        grp = (~cond).cumsum()
        return cond.groupby(grp).cumsum().astype(int)