from com.willy.binance.enums.binance_product import BinanceProduct
from com.willy.binance.strategy.moving_average_strategy import MovingAverageStrategy
from com.willy.binance.util import type_util

if __name__ == '__main__':
    MovingAverageStrategy("ma_with_ma25_0101_1130_no_stop_profit", type_util.str_to_datetime("2025-01-01T00:00:00Z"),
                          type_util.str_to_datetime("2025-11-30T00:00:00Z"), 6000
                          , BinanceProduct.BTCUSDT, 20, {}).run_backtest()
