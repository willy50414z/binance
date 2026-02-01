from enum import Enum

from binance import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET, ORDER_TYPE_STOP_LOSS


class OrderType(Enum):
    def __init__(self, value, binance_type):
        # 注意：Enum 成員的 value 必須作為第一個參數傳入
        self._value_ = value
        # 儲存額外的屬性
        self.binance_type = binance_type

    MARKET = (1, ORDER_TYPE_MARKET)
    LIMIT = (2, ORDER_TYPE_LIMIT)
    STOP_LOSS = (3, ORDER_TYPE_STOP_LOSS)
