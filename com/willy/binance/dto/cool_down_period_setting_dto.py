from dataclasses import dataclass
from datetime import datetime


@dataclass
class CoolDownPeriodSettingDto:
    loss_count: int
    cool_down_period: int
    next_trade_time: datetime = None
    last_loss_time: datetime = None
