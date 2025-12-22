import numpy as np
import pandas as pd


def append_ma(kline_df: pd.DataFrame, interval: int):
    kline_df['ma' + str(interval)] = kline_df['close'].rolling(window=interval, min_periods=interval).mean().round(2)


def append_rsi(kline_df: pd.DataFrame, windows: int):
    """相對強弱指數 (RSI) - 使用 Wilder's Smoothing"""
    delta = kline_df['close'].diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))

    # 使用 Wilder's Exponential Moving Average (與 TradingView 一致)
    avg_gain = gain.ewm(alpha=1 / windows, min_periods=windows, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / windows, min_periods=windows, adjust=False).mean()

    rs = avg_gain / avg_loss
    kline_df['rsi'] = (100 - (100 / (1 + rs))).round(2)


def append_atr(kline_df: pd.DataFrame, windows: int, mean_windows: int = 20):
    """
    平均真實波幅 (ATR) 及其移動平均線
    :param windows: ATR 的計算週期 (通常為 14)
    :param mean_windows: ATR 平均值的計算週期 (常用於判斷波動是否過低)
    """
    high = kline_df['high']
    low = kline_df['low']
    prev_close = kline_df['close'].shift(1)

    # 計算真實波幅 (TR)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # 1. 計算當前 ATR (Wilder's Smoothing)
    atr_col_name = f'atr'
    kline_df[atr_col_name] = tr.ewm(alpha=1 / windows, min_periods=windows, adjust=False).mean().round(2)

    # 2. 計算 ATR 的平均值 (ATR Mean 20)
    # 我們使用簡單移動平均 (SMA) 來計算 ATR 的平均基準
    kline_df[f'atr_mean'] = kline_df[atr_col_name].rolling(window=mean_windows).mean().round(2)


def append_adx(kline_df: pd.DataFrame, windows: int):
    """趨勢強度指標 (ADX)"""
    high = kline_df['high']
    low = kline_df['low']
    close = kline_df['close']
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    # 1. 計算 True Range (TR)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / windows, min_periods=windows, adjust=False).mean()

    # 2. 計算 Directional Movement (+DM, -DM)
    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    # 3. 計算平滑後的 DM
    plus_di = 100 * (pd.Series(plus_dm, index=kline_df.index).ewm(alpha=1 / windows, adjust=False).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm, index=kline_df.index).ewm(alpha=1 / windows, adjust=False).mean() / atr)

    # 4. 計算 DX 並平滑得到 ADX
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    kline_df['adx'] = dx.ewm(alpha=1 / windows, min_periods=windows, adjust=False).mean().round(2)
    # 可選：保存 DI+ 和 DI-
    kline_df['plus_di' + str(windows)] = plus_di.round(2)
    kline_df['minus_di' + str(windows)] = minus_di.round(2)


def append_is_ma25_keep_grow(kline_df: pd.DataFrame, windows):
    # ma25 過去20天是否連續上漲
    kline_df['ma25_diff'] = kline_df['ma25'].diff()
    diff_int = kline_df['ma25_diff'] > 0
    diff_int = diff_int.astype(int)
    is_ma25_keep_grow = diff_int.rolling(window=windows, min_periods=windows).min()
    kline_df['is_ma25_keep_grow'] = is_ma25_keep_grow.astype(bool)


def append_is_ma25_keep_fall(kline_df: pd.DataFrame, windows):
    # ma25 過去20天是否連續下跌
    kline_df['ma25_diff'] = kline_df['ma25'].diff()
    diff_ma25_diff = kline_df['ma25_diff'] < 0
    diff_int = diff_ma25_diff.astype(int)
    is_ma25_keep_fall = diff_int.rolling(window=windows, min_periods=windows).min()
    kline_df['is_ma25_keep_fall'] = is_ma25_keep_fall.astype(bool)


def append_ma7_and_ma25_rel(kline_df: pd.DataFrame, windows):
    diff_sign = np.sign(kline_df['ma7'] - kline_df['ma25'])  # 1, 0, -1

    ma_rel = []
    current_len = 0
    current_sign = 0
    for s in diff_sign:
        if s == 0:
            # 無方向性，重置
            current_len = 0
            current_sign = 0
            ma_rel.append(0)
        elif np.isnan(s):
            ma_rel.append(0)
        else:
            if s == current_sign:
                current_len += 1
            else:
                current_len = 1
                current_sign = s
            # 將日數轉成輸出值，前提是你要的輸出就是日數本身
            ma_rel.append(current_len * int(np.sign(current_sign)))

    kline_df['ma7_and_ma25_rel'] = ma_rel
    kline_df['last_ma7_and_ma25_rel'] = kline_df['ma7_and_ma25_rel'].shift(1)
