from enum import Enum


class TechIdxType(Enum):
    def __init__(self, method_name, base_window, warm_up_multiplier):
        self.method_name = method_name
        self.base_window = base_window
        self.warm_up_multiplier = warm_up_multiplier

    # 簡單移動平均: 剛好 N 個週期即可
    SMA_7 = ("append_ma", 7, 1.0)
    SMA_6 = ("append_ma", 6, 1.0)
    SMA_25 = ("append_ma", 25, 1.0)
    SMA_200 = ("append_ma", 200, 1.0)

    # 強力平滑指標: 建議 5 倍週期，否則數值會飄移
    RSI_14 = ("append_rsi", 14, 5.0)
    ATR_14 = ("append_atr", 14, 5.0)
    ADX_14 = ("append_adx", 14, 5.0)

    # 客製化指標
    IS_MA25_KEEP_GROW_20 = ("append_is_ma25_keep_grow", 20, 1.0)
    IS_MA25_KEEP_FALL_20 = ("append_is_ma25_keep_fall", 20, 1.0)
    MA7_AND_MA25_REL = ("append_ma7_and_ma25_rel", 25, 1.0)
