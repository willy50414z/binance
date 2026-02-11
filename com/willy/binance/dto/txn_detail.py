from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from com.willy.binance.dto.cool_down_period_dto import CoolDownPeriodDto
from com.willy.binance.dto.trade_record import TradeRecord


@dataclass
class TxnDetail:
    date: datetime
    units: Decimal
    handle_amt: Decimal
    handling_fee: Decimal
    guarantee_fee: Decimal
    current_price: Decimal
    profit: Decimal
    profit_ratio: Decimal
    total_profit: Decimal
    force_close_offset_price: Decimal | None
    break_even_point_price: Decimal | None
    max_loss: Decimal
    acct_balance: Decimal
    trade_record: TradeRecord | None
    cool_down_period: Optional[CoolDownPeriodDto] = None
