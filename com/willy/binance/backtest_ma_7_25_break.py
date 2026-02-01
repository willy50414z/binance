from decimal import Decimal

from com.willy.binance.dto.cool_down_period_setting_dto import CoolDownPeriodSettingDto
from com.willy.binance.enums.binance_product import BinanceProduct
from com.willy.binance.strategy.ma_7_25_break_strategy import Ma725BreakStrategy, Ma725BreakIndexSwitch
from com.willy.binance.util import type_util

if __name__ == '__main__':
    strategy = Ma725BreakStrategy(f"bot_ma_7_25_break",
                                  type_util.str_to_datetime(f"2025-11-11T00:00:00Z"),
                                  type_util.str_to_datetime(f"2026-01-30T00:00:00Z"), Decimal("6000")
                                  , BinanceProduct.BTCUSDT, Decimal("20"), {}, CoolDownPeriodSettingDto(2, 96))

    strategy.cross_test_config = {Ma725BreakIndexSwitch.KEEP: True, Ma725BreakIndexSwitch.FAKE_BREAK: True
        , Ma725BreakIndexSwitch.RSI: True, Ma725BreakIndexSwitch.ATR: True}
    strategy.run_backtest()
