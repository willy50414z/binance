import numpy as np
import pandas as pd
import talib

SMA_PERIODS = [7, 25, 99]
EMA_PERIODS = [7, 25, 99]
MACD_FAST_PERIOD = 12
MACD_SLOW_PERIOD = 26
MACD_SIGNAL_PERIOD = 9
ADX_PERIOD = 14
RSI_PERIOD = 14
KDJ_FASTK_PERIOD = 9
KDJ_SLOWK_PERIOD = 3
KDJ_SLOWD_PERIOD = 3
CCI_PERIOD = 14
BBANDS_PERIOD = 20
BBANDS_NBDEV = 2
ATR_PERIOD = 14
MFI_PERIOD = 14

TECHNICAL_INDICATOR_COLUMNS = [
    *[f"sma_{period}" for period in SMA_PERIODS],
    *[f"ema_{period}" for period in EMA_PERIODS],
    f"macd_fast_ema_{MACD_FAST_PERIOD}",
    f"macd_slow_ema_{MACD_SLOW_PERIOD}",
    "macd",
    "macd_signal",
    "macd_hist",
    f"adx_{ADX_PERIOD}",
    f"rsi_{RSI_PERIOD}",
    "kdj_k",
    "kdj_d",
    "kdj_j",
    f"cci_{CCI_PERIOD}",
    "bb_upper",
    "bb_middle",
    "bb_lower",
    f"atr_{ATR_PERIOD}",
    "obv",
    "vwap",
    f"mfi_{MFI_PERIOD}",
]


def _resolve_volume_column(ohlcv_df: pd.DataFrame) -> str:
    if "vol" in ohlcv_df.columns:
        return "vol"
    if "volume" in ohlcv_df.columns:
        return "volume"
    raise ValueError("OHLCV dataframe must contain 'vol' or 'volume' column.")


def append_technical_indicators(ohlcv_df: pd.DataFrame) -> pd.DataFrame:
    if ohlcv_df is None or ohlcv_df.empty:
        return ohlcv_df

    required_columns = ["open", "high", "low", "close"]
    missing_columns = [column for column in required_columns if column not in ohlcv_df.columns]
    if missing_columns:
        raise ValueError(f"OHLCV dataframe missing required columns: {missing_columns}")

    volume_column = _resolve_volume_column(ohlcv_df)
    tech_df = ohlcv_df.copy()

    open_price = pd.to_numeric(tech_df["open"], errors="coerce").astype("float64")
    high_price = pd.to_numeric(tech_df["high"], errors="coerce").astype("float64")
    low_price = pd.to_numeric(tech_df["low"], errors="coerce").astype("float64")
    close_price = pd.to_numeric(tech_df["close"], errors="coerce").astype("float64")
    volume = pd.to_numeric(tech_df[volume_column], errors="coerce").astype("float64")

    for period in SMA_PERIODS:
        tech_df[f"sma_{period}"] = talib.SMA(close_price, timeperiod=period)
    for period in EMA_PERIODS:
        tech_df[f"ema_{period}"] = talib.EMA(close_price, timeperiod=period)

    tech_df[f"macd_fast_ema_{MACD_FAST_PERIOD}"] = talib.EMA(close_price, timeperiod=MACD_FAST_PERIOD)
    tech_df[f"macd_slow_ema_{MACD_SLOW_PERIOD}"] = talib.EMA(close_price, timeperiod=MACD_SLOW_PERIOD)

    macd, macd_signal, macd_hist = talib.MACD(
        close_price,
        fastperiod=MACD_FAST_PERIOD,
        slowperiod=MACD_SLOW_PERIOD,
        signalperiod=MACD_SIGNAL_PERIOD,
    )
    tech_df["macd"] = macd
    tech_df["macd_signal"] = macd_signal
    tech_df["macd_hist"] = macd_hist

    tech_df[f"adx_{ADX_PERIOD}"] = talib.ADX(
        high_price,
        low_price,
        close_price,
        timeperiod=ADX_PERIOD,
    )
    tech_df[f"rsi_{RSI_PERIOD}"] = talib.RSI(close_price, timeperiod=RSI_PERIOD)

    kdj_k, kdj_d = talib.STOCH(
        high_price,
        low_price,
        close_price,
        fastk_period=KDJ_FASTK_PERIOD,
        slowk_period=KDJ_SLOWK_PERIOD,
        slowk_matype=0,
        slowd_period=KDJ_SLOWD_PERIOD,
        slowd_matype=0,
    )
    tech_df["kdj_k"] = kdj_k
    tech_df["kdj_d"] = kdj_d
    tech_df["kdj_j"] = (3 * kdj_k) - (2 * kdj_d)

    tech_df[f"cci_{CCI_PERIOD}"] = talib.CCI(
        high_price,
        low_price,
        close_price,
        timeperiod=CCI_PERIOD,
    )

    bb_upper, bb_middle, bb_lower = talib.BBANDS(
        close_price,
        timeperiod=BBANDS_PERIOD,
        nbdevup=BBANDS_NBDEV,
        nbdevdn=BBANDS_NBDEV,
        matype=0,
    )
    tech_df["bb_upper"] = bb_upper
    tech_df["bb_middle"] = bb_middle
    tech_df["bb_lower"] = bb_lower

    tech_df[f"atr_{ATR_PERIOD}"] = talib.ATR(
        high_price,
        low_price,
        close_price,
        timeperiod=ATR_PERIOD,
    )
    tech_df["obv"] = talib.OBV(close_price, volume)

    typical_price = (high_price + low_price + close_price) / 3.0
    cumulative_tpv = (typical_price * volume).cumsum()
    cumulative_volume = volume.cumsum()
    tech_df["vwap"] = (cumulative_tpv / cumulative_volume).replace([np.inf, -np.inf], np.nan)

    tech_df[f"mfi_{MFI_PERIOD}"] = talib.MFI(
        high_price,
        low_price,
        close_price,
        volume,
        timeperiod=MFI_PERIOD,
    )

    return tech_df
