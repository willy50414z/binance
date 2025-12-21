import numpy as np
import pandas as pd


def append_ma(kline_df: pd.DataFrame, interval: int):
    kline_df['ma' + str(interval)] = kline_df['close'].rolling(window=interval, min_periods=interval).mean().round(
        2)


def append_is_ma25_keep_grow(kline_df: pd.DataFrame, windows):
    # ma25 過去20天是否連續上漲
    kline_df['ma25_diff'] = kline_df['ma25'].diff()
    diff_int = kline_df['ma25_diff'] > 0
    diff_int = diff_int.astype(int)
    is_ma25_keep_grow = diff_int.rolling(window=windows, min_periods=windows).min()
    kline_df['is_ma25_keep_grow_' + str(windows)] = is_ma25_keep_grow.astype(bool)


def append_is_ma25_keep_fall(kline_df: pd.DataFrame, windows):
    # ma25 過去20天是否連續下跌
    kline_df['ma25_diff'] = kline_df['ma25'].diff()
    diff_ma25_diff = kline_df['ma25_diff'] < 0
    diff_int = diff_ma25_diff.astype(int)
    is_ma25_keep_fall = diff_int.rolling(window=windows, min_periods=windows).min()
    kline_df['is_ma25_keep_fall_' + str(windows)] = is_ma25_keep_fall.astype(bool)


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
