from dataclasses import dataclass
from typing import List

from com.willy.binance.dto.txn_detail import TxnDetail


@dataclass
class TradeDetail:
    txn_detail_list: List[TxnDetail]
