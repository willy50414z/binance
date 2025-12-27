from com.willy.binance.dto.cool_down_period_setting_dto import CoolDownPeriodSettingDto
from com.willy.binance.enums.binance_product import BinanceProduct
from com.willy.binance.service import strategy_idx_cross_test_svc
from com.willy.binance.strategy.moving_average_strategy import MovingAverageStrategy
from com.willy.binance.util import type_util

if __name__ == '__main__':
    strategy = MovingAverageStrategy
    test_args = ("ma_with_ma25_0101_1130_no_stop_profit_germini_ooo",
                 type_util.str_to_datetime("2025-01-01T00:00:00Z"),
                 type_util.str_to_datetime("2025-12-21T00:00:00Z"), 6000
                 , BinanceProduct.BTCUSDT, 20, {}, CoolDownPeriodSettingDto(2, 96))

    strategy_idx_cross_test_svc.start(strategy, test_args)
