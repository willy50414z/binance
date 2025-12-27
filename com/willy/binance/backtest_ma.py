from decimal import Decimal

from com.willy.binance.dto.cool_down_period_setting_dto import CoolDownPeriodSettingDto
from com.willy.binance.enums.binance_product import BinanceProduct
from com.willy.binance.strategy.moving_average_strategy import MovingAverageStrategy, MaIndexSwitch
from com.willy.binance.util import type_util

if __name__ == '__main__':
    strategy = MovingAverageStrategy("ma_with_ma25_0101_1130_no_stop_profit_backtest_mappp",
                                     type_util.str_to_datetime("2025-01-01T00:00:00Z"),
                                     type_util.str_to_datetime("2025-12-21T00:00:00Z"), Decimal("6000")
                                     , BinanceProduct.BTCUSDT, Decimal("20"), {}, CoolDownPeriodSettingDto(2, 96))

    strategy.cross_test_config = {MaIndexSwitch.KEEP: True, MaIndexSwitch.FAKE_BREAK: True
        , MaIndexSwitch.RSI: True, MaIndexSwitch.ATR: True}
    strategy.run_backtest()
