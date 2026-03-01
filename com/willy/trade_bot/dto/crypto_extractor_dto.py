from dataclasses import dataclass
from datetime import datetime

from com.willy.trade_bot.enums.exchange import Exchange
from com.willy.trade_bot.enums.market_type import MarketType
from com.willy.trade_bot.enums.product import Product
from com.willy.trade_bot.enums.timeframe import Timeframe


@dataclass
class CryptoExtractorDto:
    exchange: Exchange
    product: Product
    market_type: MarketType
    timeframe: Timeframe
    start_dt: datetime
    end_dt: datetime
