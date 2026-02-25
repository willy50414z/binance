import logging
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy, merge_informative_pair
from pandas import DataFrame
import numpy as np

logger = logging.getLogger(__name__)


class AMRS4_1Strategy_v12(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 120

    # --- 核心參數 ---
    minimal_roi = {"0": 10.0}
    stoploss = -0.05  # 5% 硬性止損

    # 稍微放寬移動止盈，給行情更多呼吸空間
    trailing_stop = True
    trailing_stop_positive = 0.005  # 0.5% 啟動
    trailing_stop_positive_offset = 0.015  # 獲利 1.5% 後啟動更嚴格跟隨
    trailing_only_offset_is_reached = True

    ma7_len, ma25_len, ma99_len = 7, 25, 99

    # 【v12 新增參數】
    exit_ma25_confirm = 3  # 連續 3 根收盤 > MA25
    exit_bull_streak = 4  # 連續 4 根陽 K 且收盤 > MA7

    def informative_pairs(self):
        return [(self.config['stake_currency'], '1d')]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. 日線數據 (維持 v10 的強大濾網)
        informative = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='1d')
        informative['ma25_day'] = ta.SMA(informative, timeperiod=25)
        informative['day_slope'] = informative['ma25_day'].diff()
        informative['adx'] = ta.ADX(informative, timeperiod=14)
        informative['minus_di'] = ta.MINUS_DI(informative, timeperiod=14)
        informative['plus_di'] = ta.PLUS_DI(informative, timeperiod=14)

        dataframe = merge_informative_pair(dataframe, informative, self.timeframe, '1d', ffill=True)

        # 2. 15m 指標
        dataframe["ma7"] = ta.SMA(dataframe, timeperiod=self.ma7_len)
        dataframe["ma25"] = ta.SMA(dataframe, timeperiod=self.ma25_len)
        dataframe["ma99"] = ta.SMA(dataframe, timeperiod=self.ma99_len)
        dataframe["ma7_slope"] = dataframe["ma7"].diff()
        dataframe["ma25_slope"] = dataframe["ma25"].diff()

        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=5).mean()

        # 進場形態
        dataframe['body_min'] = np.minimum(dataframe['open'], dataframe['close'])
        dataframe['ten_candle_low'] = dataframe['body_min'].shift(1).rolling(window=10).min()
        dataframe['body_size'] = dataframe['open'] - dataframe['close']
        dataframe['is_bull'] = dataframe['close'] > dataframe['open']

        # 【v12 出場邏輯判定計算】
        # 條件 A: 收盤 > MA25
        dataframe["close_gt_ma25"] = dataframe["close"] > dataframe["ma25"]
        dataframe["streak_ma25"] = self._streak_true(dataframe["close_gt_ma25"])

        # 條件 B: 陽線 且 收盤 > MA7
        dataframe["bull_above_ma7"] = (dataframe['is_bull']) & (dataframe['close'] > dataframe['ma7'])
        dataframe["streak_bull"] = self._streak_true(dataframe["bull_above_ma7"])

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 進場條件維持 v10 Shield 強大設定，只抓「大趨勢」
        base_filter = (
                (dataframe["close"] < dataframe["ma99"]) &
                (dataframe["ma7"] < dataframe["ma25"]) &
                (dataframe["ma7_slope"] < 0) &
                (dataframe["ma25_slope"] < 0) &
                (dataframe["close"] < dataframe["ten_candle_low"]) &
                (dataframe["body_size"] >= (dataframe['atr'] * 1.5))  # 稍微收緊至 1.5
        )

        macro_filter = (
                (dataframe['day_slope_1d'] <= 0) &
                (dataframe['adx_1d'] > 20) &  # ADX 門檻調高到 20，更嚴選
                (dataframe['minus_di_1d'] > dataframe['plus_di_1d'])
        )

        entry_condition = base_filter & macro_filter

        dataframe.loc[entry_condition, "enter_short"] = 1
        dataframe.loc[entry_condition, "enter_tag"] = "v12_sniper_entry"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 【v12 出場核心升級】
        exit_condition = (
                (dataframe["streak_ma25"] >= self.exit_ma25_confirm) |  # 連 3 根突破 MA25
                (dataframe["streak_bull"] >= self.exit_bull_streak)  # 連 4 根高於 MA7 的陽 K
        )

        dataframe.loc[exit_condition, "exit_short"] = 1
        dataframe.loc[exit_condition, "exit_tag"] = "v12_trend_reversal_exit"
        return dataframe

    @staticmethod
    def _streak_true(cond: pd.Series) -> pd.Series:
        cond = cond.fillna(False).astype(bool)
        grp = (~cond).cumsum()
        return cond.groupby(grp).cumsum().astype(int)