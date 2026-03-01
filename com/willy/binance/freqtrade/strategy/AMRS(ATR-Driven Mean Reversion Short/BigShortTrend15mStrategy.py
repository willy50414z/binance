# pragma pylint: disable=missing-module-docstring, invalid-name, pointless-string-statement
import logging
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair

logger = logging.getLogger(__name__)


class BigShortTrend15mStrategy(IStrategy):
    """
    目標：捕捉 15m 放空「大行情」（趨勢延伸），避免盤整假破底反覆被洗。

    核心設計：
    - 1H 大方向濾網（只在結構空頭做空）
    - 15m 動能破底入場（rolling low + buffer）
    - ADX 濾網（只做趨勢段）
    - 波動尺度一致（實體長度以 ATR 倍數判斷，取代固定點數）
    - 出場用「ATR 反彈追蹤」保留右尾（類似 Chandelier / trailing for short）
    - 另加 time-stop，避免卡在不動/盤整

    注意：參數需要依標的特性微調（加密/期貨/股票波動不同）。
    """

    INTERFACE_VERSION = 3

    timeframe = "15m"
    informative_timeframe = "1h"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 240

    # --- 基本風控/行為 ---
    minimal_roi = {"0": 10.0}  # 幾乎不使用 ROI 出場，主要靠 exit signal / custom_exit
    stoploss = -0.06          # 硬停損先保守設定；趨勢策略靠濾網 + trailing exit 取得右尾

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    # --- 可調參數（先給一組偏保守且趨勢導向的初始值） ---
    # Trend filter (1H)
    htf_fast = 25
    htf_slow = 99
    htf_adx_len = 14
    htf_adx_min = 20

    # Entry (15m)
    ltf_ema_fast = 7
    ltf_ema_mid = 25
    ltf_ema_slow = 99

    atr_len = 14
    adx_len = 14
    adx_min = 18

    breakout_lookback = 16       # 16 * 15m = 4h
    breakout_buffer = 0.003      # 0.3% 確認破底（避免假破）

    body_atr_mult = 0.9          # 實體 >= ATR * 0.9 才算有動能（取代固定點數）
    volume_min = 0

    # Exit / trailing
    trail_atr_mult = 2.5         # 價格從「最低點」反彈 >= ATR*2.5 觸發出場（short trailing）
    hard_exit_ema = 25           # 15m 收盤站上 EMA25 視作趨勢轉弱，提前出場
    time_stop_candles = 64       # 64 * 15m = 16h
    time_stop_profit = 0.01      # 16h 還沒 >1%（short），就考慮離場（避免盤整耗損）

    def informative_pairs(self):
        # 需要 1H 資料做大方向濾網
        pairs = self.dp.current_whitelist()
        return [(pair, self.informative_timeframe) for pair in pairs]

    @staticmethod
    def _slope(series: pd.Series, n: int = 3) -> pd.Series:
        """
        以 n 根差分近似斜率（不做回歸，計算快且足夠用於濾網）
        """
        return series.diff(n)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- LTF (15m) ---
        dataframe["ema7"] = ta.EMA(dataframe, timeperiod=self.ltf_ema_fast)
        dataframe["ema25"] = ta.EMA(dataframe, timeperiod=self.ltf_ema_mid)
        dataframe["ema99"] = ta.EMA(dataframe, timeperiod=self.ltf_ema_slow)

        dataframe["adx"] = ta.ADX(dataframe, timeperiod=self.adx_len)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_len)

        # rolling low（用 low，而不是 body_min，趨勢破底更貼近「真的跌破」）
        dataframe["roll_low"] = dataframe["low"].shift(1).rolling(self.breakout_lookback).min()

        # 動能：實體（做空時希望 close < open 且夠大）
        dataframe["body"] = (dataframe["open"] - dataframe["close"]).astype(float)

        # LTF 斜率（用於避免明顯走平）
        dataframe["ema25_slope"] = self._slope(dataframe["ema25"], n=3)
        dataframe["ema99_slope"] = self._slope(dataframe["ema99"], n=3)

        # --- HTF (1h) ---
        inf = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=self.informative_timeframe)

        inf["htf_ema25"] = ta.EMA(inf, timeperiod=self.htf_fast)
        inf["htf_ema99"] = ta.EMA(inf, timeperiod=self.htf_slow)
        inf["htf_adx"] = ta.ADX(inf, timeperiod=self.htf_adx_len)
        inf["htf_ema25_slope"] = self._slope(inf["htf_ema25"], n=2)
        inf["htf_ema99_slope"] = self._slope(inf["htf_ema99"], n=2)

        dataframe = merge_informative_pair(
            dataframe,
            inf,
            self.timeframe,
            self.informative_timeframe,
            ffill=True
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = None

        # 1H 結構空頭濾網：EMA25 < EMA99 且斜率向下 + ADX 夠
        htf_bear = (
            (dataframe["htf_ema25_1h"] < dataframe["htf_ema99_1h"]) &
            (dataframe["htf_ema25_slope_1h"] < 0) &
            (dataframe["htf_ema99_slope_1h"] < 0) &
            (dataframe["htf_adx_1h"] >= self.htf_adx_min)
        )

        # 15m 趨勢環境：EMA25 < EMA99，且至少不是走平
        ltf_bear = (
            (dataframe["ema25"] < dataframe["ema99"]) &
            (dataframe["ema25_slope"] < 0) &
            (dataframe["ema99_slope"] < 0)
        )

        # 15m 趨勢強度濾網：ADX
        ltf_trend = dataframe["adx"] >= self.adx_min

        # 動能破底：跌破近 N 根低點，再多 0.3% buffer 避免假破
        breakout = dataframe["close"] < (dataframe["roll_low"] * (1.0 - self.breakout_buffer))

        # 動能實體：用 ATR 倍數取代固定點數（跨標的更穩）
        momentum_body = dataframe["body"] >= (dataframe["atr"] * self.body_atr_mult)

        # 量能基本要求
        vol_ok = dataframe["volume"] > self.volume_min

        enter = htf_bear & ltf_bear & ltf_trend & breakout & momentum_body & vol_ok

        dataframe.loc[enter, "enter_short"] = 1
        dataframe.loc[enter, "enter_tag"] = "bigshort_breakdown_htf"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        先放一個「結構轉弱」的 exit signal：
        - 15m 收盤站上 EMA25（短線轉弱）
        主要的趨勢延伸出場在 custom_exit（ATR trailing / time-stop）
        """
        dataframe["exit_short"] = 0
        dataframe["exit_tag"] = None

        hard_exit = (dataframe["close"] > dataframe["ema25"]) & (dataframe["volume"] > 0)

        dataframe.loc[hard_exit, "exit_short"] = 1
        dataframe.loc[hard_exit, "exit_tag"] = "hard_exit_close_above_ema25"

        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs
    ) -> Optional[str]:
        """
        針對 short 的「右尾最大化」：
        - 以 trade.min_rate 作為入場後的最低價（對 short 來說越低越好）
        - 當價格從最低價反彈 >= ATR * trail_atr_mult 觸發出場（類似 Chandelier / trailing）
        - 加 time-stop：持倉太久但沒賺到該賺的就走（避免盤整耗損）
        """
        df: DataFrame = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty:
            return None

        last = df.iloc[-1]
        atr = float(last.get("atr", np.nan))
        if not np.isfinite(atr) or atr <= 0:
            return None

        # --- ATR trailing for short ---
        # trade.min_rate：交易期間的最低成交價（short 有利）
        trough = trade.min_rate if trade.min_rate else current_rate

        # 反彈止盈線：最低點 + ATR * k
        rebound_stop = trough + (atr * self.trail_atr_mult)

        if current_rate >= rebound_stop:
            return "atr_trailing_rebound"

        # --- Time stop ---
        # 用分鐘換算 15m K 數
        minutes_in_trade = (current_time - trade.open_date_utc).total_seconds() / 60.0
        candles_in_trade = minutes_in_trade / 15.0

        if candles_in_trade >= self.time_stop_candles and current_profit < self.time_stop_profit:
            return "time_stop_no_followthrough"

        return None