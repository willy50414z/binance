from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CoolDownPeriodSettingDto:
    loss_count: int
    cool_down_period: int
    next_trade_time: Optional[datetime] = None
    last_loss_time: Optional[datetime] = None
