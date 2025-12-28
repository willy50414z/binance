from enum import Enum


class TradeType(Enum):
    BUY = 1, "BUY"
    SELL = 2, "SELL"

    def __new__(cls, value, binance_type):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.binance_type = binance_type
        return obj
