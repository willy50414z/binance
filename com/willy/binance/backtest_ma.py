from com.willy.binance.enums.binance_product import BinanceProduct
from com.willy.binance.strategy.moving_average_strategy import MovingAverageStrategy, MaIndexSwitch
from com.willy.binance.util import type_util

if __name__ == '__main__':
    strategy = MovingAverageStrategy("ma_with_ma25_0101_1130_no_stop_profit_01_12",
                                     # type_util.str_to_datetime("2025-11-01T00:00:00Z"),
                                     type_util.str_to_datetime("2025-01-01T00:00:00Z"),
                                     type_util.str_to_datetime("2025-11-30T00:00:00Z"), 6000
                                     , BinanceProduct.BTCUSDT, 20, {})

    strategy.cross_test_config = {MaIndexSwitch.KEEP: True}
    strategy.run_backtest()
