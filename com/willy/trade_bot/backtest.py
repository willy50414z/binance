from com.willy.trade_bot.dto.backtest_config import BackTestConfig
from com.willy.trade_bot.enums.exchange import Exchange
from com.willy.trade_bot.enums.market_type import MarketType
from com.willy.trade_bot.enums.product import Product
from com.willy.trade_bot.enums.timeframe import Timeframe
from com.willy.trade_bot.service.backtest_svc import BackTestService
from com.willy.trade_bot.utils import type_utils

if __name__ == '__main__':
    back_test_svc = BackTestService(
        BackTestConfig(Exchange.BINANCE, Product.BTCUSDT, MarketType.FUTURE, Timeframe.MINUTE_15,
                       type_utils.str_to_datetime(f"2025-11-11T00:00:00Z")
                       , type_utils.str_to_datetime(f"2025-12-11T00:00:00Z")
                       ))
    back_test_svc.download_test_data()
