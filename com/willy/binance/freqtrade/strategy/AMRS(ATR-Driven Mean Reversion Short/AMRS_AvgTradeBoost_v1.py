import logging
from datetime import timedelta

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy, merge_informative_pair
from freqtrade.persistence import Trade

logger = logging.getLogger(__name__)


class AMRS_AvgTradeBoost_v1(IStrategy):
    """
    目標：提高「平均單筆交易報酬率」
    手段：
      1) 降低震盪盤假訊號：加強 1D + 4H regime filter（ADX、DI、斜率）
      2) 降低低品質進場：動能確認更嚴格（RSI 更低 + 放量）& 提高 ATR/body 門檻
      3) 更早砍無效單：exit_confirm 降到 1 + early invalidation + time-stop
    """

    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 240  # 給 4h/1d 指標更充足的 warmup

    # --- ROI / Stop / Trailing ---
    minimal_roi = {"0": 10.0}   # 幾乎不靠 ROI 出場
    stoploss = -0.05

    trailing_stop = True
    trailing_stop_positive = 0.0025            # 0.25%
    trailing_stop_positive_offset = 0.012      # 1.2% (比 v10 更要求「先跑出空間」)
    trailing_only_offset_is_reached = True

    # --- Core params (你可自行微調) ---
    ma7_len, ma25_len, ma99_len = 7, 25, 99
    lookback_candles = 10

    # 出場確認根數：更早砍無效單
    exit_confirm_candles = 1

    # 進場嚴格度：提高每筆的「波動空間」以對抗摩擦成本
    atr_body_mult = 1.7         # v10=1.4 -> 提高到 1.7
    atr_pct_min = 0.004         # ATR/close 至少 0.4%（可依你交易所費率微調）

    # 動能確認（兩段式）
    rsi_hard = 20               # 非常弱勢：直接允許
    rsi_soft = 28               # 偏弱勢：需搭配放量
    vol_mult = 2.0              # 放量倍數（相對 5 根均量）

    # 1D regime filter
    adx_1d_min = 25
    di_gap_1d = 3               # (-DI) - (+DI) 至少差多少

    # 4H regime filter（擋盤整，讓單筆更有趨勢空間）
    adx_4h_min = 20

    # custom_exit：無效單早退 / 久盤 time-stop
    early_invalidation_loss = -0.003  # -0.3% 且型態失效 -> 早退
    time_stop_minutes = 90
    flat_band = 0.002                 # +/-0.2% 視為「磨在成本附近」

    def informative_pairs(self):
        """
        修正：抓 whitelist 每個 pair 的 1D + 4H
        """
        pairs = []
        try:
            pairs = self.dp.current_whitelist()
        except Exception:
            # 某些模式下 dp 可能未就緒，保守回傳空
            return []
        return [(p, "1d") for p in pairs] + [(p, "4h") for p in pairs]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        # ========= 1D =========
        inf_1d = self.dp.get_pair_dataframe(pair=pair, timeframe="1d")
        inf_1d["ma25"] = ta.SMA(inf_1d, timeperiod=25)
        inf_1d["ma25_slope"] = inf_1d["ma25"].diff()
        inf_1d["adx"] = ta.ADX(inf_1d, timeperiod=14)
        inf_1d["plus_di"] = ta.PLUS_DI(inf_1d, timeperiod=14)
        inf_1d["minus_di"] = ta.MINUS_DI(inf_1d, timeperiod=14)

        dataframe = merge_informative_pair(dataframe, inf_1d, self.timeframe, "1d", ffill=True)

        # ========= 4H =========
        inf_4h = self.dp.get_pair_dataframe(pair=pair, timeframe="4h")
        inf_4h["ma25"] = ta.SMA(inf_4h, timeperiod=25)
        inf_4h["ma25_slope"] = inf_4h["ma25"].diff()
        inf_4h["adx"] = ta.ADX(inf_4h, timeperiod=14)
        inf_4h["plus_di"] = ta.PLUS_DI(inf_4h, timeperiod=14)
        inf_4h["minus_di"] = ta.MINUS_DI(inf_4h, timeperiod=14)

        dataframe = merge_informative_pair(dataframe, inf_4h, self.timeframe, "4h", ffill=True)

        # ========= 15m base =========
        dataframe["ma7"] = ta.SMA(dataframe, timeperiod=self.ma7_len)
        dataframe["ma25"] = ta.SMA(dataframe, timeperiod=self.ma25_len)
        dataframe["ma99"] = ta.SMA(dataframe, timeperiod=self.ma99_len)
        dataframe["ma7_slope"] = dataframe["ma7"].diff()
        dataframe["ma25_slope"] = dataframe["ma25"].diff()

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["volume_mean"] = dataframe["volume"].rolling(window=5).mean()

        # v10 形態：跌破近 N 根 body low + 大黑 K
        dataframe["body_min"] = np.minimum(dataframe["open"], dataframe["close"])
        dataframe["ten_candle_low"] = dataframe["body_min"].shift(1).rolling(window=self.lookback_candles).min()
        dataframe["body_size"] = dataframe["open"] - dataframe["close"]  # 空頭大黑K: open > close -> 正值

        # exit streak (close > ma7) 連續根數
        dataframe["close_gt_ma7"] = dataframe["close"] > dataframe["ma7"]
        dataframe["streak_ma7"] = self._streak_true(dataframe["close_gt_ma7"])

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 15m 形態條件（更嚴格，讓每筆有足夠空間） ---
        base_filter = (
            (dataframe["volume"] > 0) &
            (dataframe["close"] < dataframe["ma99"]) &
            (dataframe["ma7"] < dataframe["ma25"]) &
            (dataframe["ma7_slope"] < 0) &
            (dataframe["ma25_slope"] < 0) &
            (dataframe["close"] < dataframe["ten_candle_low"]) &
            (dataframe["body_size"] >= (dataframe["atr"] * self.atr_body_mult)) &
            (dataframe["atr_pct"] >= self.atr_pct_min)
        )

        # --- 動能確認：兩段式（更少交易，但每筆更「像真的」） ---
        momentum_confirm = (
            (dataframe["rsi"] <= self.rsi_hard) |
            ((dataframe["rsi"] <= self.rsi_soft) & (dataframe["volume"] > dataframe["volume_mean"] * self.vol_mult))
        )

        # --- 1D regime filter：更嚴格，擋盤整 ---
        macro_1d = (
            (dataframe["ma25_slope_1d"] < 0) &
            (dataframe["adx_1d"] >= self.adx_1d_min) &
            ((dataframe["minus_di_1d"] - dataframe["plus_di_1d"]) >= self.di_gap_1d)
        )

        # --- 4H regime filter：再擋一次盤整 / 無趨勢 ---
        macro_4h = (
            (dataframe["ma25_slope_4h"] < 0) &
            (dataframe["adx_4h"] >= self.adx_4h_min) &
            (dataframe["minus_di_4h"] > dataframe["plus_di_4h"])
        )

        entry_condition = base_filter & momentum_confirm & macro_1d & macro_4h

        dataframe.loc[entry_condition, "enter_short"] = 1
        dataframe.loc[entry_condition, "enter_tag"] = "avgboost_breakdown_short"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 更早認錯：只要回到 MA7 上方就出（搭配 custom_exit 更精細）
        dataframe.loc[dataframe["streak_ma7"] >= self.exit_confirm_candles, "exit_short"] = 1

        # 保底：明顯回抽到 MA25 上方也退出（避免拖）
        dataframe.loc[dataframe["close"] > (dataframe["ma25"] * 1.0005), "exit_short"] = 1

        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs
    ):
        """
        1) 無效單早退：小虧且型態失效（回到 MA7 上）就走，別被 exit_signal 磨很久
        2) time-stop：開倉太久還在成本附近，直接走（降低摩擦成本佔比）
        3) 快速獲利保護：有利潤且回到 MA7 上 -> 收
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None

        last = dataframe.iloc[-1].squeeze()

        # (1) 無效單早退：已經小虧 + 回到 MA7 上方（對空單就是失效）
        if current_profit <= self.early_invalidation_loss and last["close"] > last["ma7"]:
            return "early_invalidation"

        # (2) time-stop：久盤磨手續費
        if current_time - trade.open_date_utc > timedelta(minutes=self.time_stop_minutes):
            if -self.flat_band <= current_profit <= self.flat_band:
                return "time_stop_flat"

        # (3) 快速獲利保護（你原本 v10 的 quick profit 概念延伸）
        if current_profit > 0.007 and last["close"] > last["ma7"]:
            return "quick_profit_protect"

        return None

    @staticmethod
    def _streak_true(cond: pd.Series) -> pd.Series:
        cond = cond.fillna(False).astype(bool)
        grp = (~cond).cumsum()
        return cond.groupby(grp).cumsum().astype(int)