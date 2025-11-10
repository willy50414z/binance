from datetime import datetime
from decimal import Decimal
from typing import List
import numpy as np
from binance import Client
from dateutil.relativedelta import relativedelta

from com.willy.binance.enums.binance_product import BinanceProduct
from com.willy.binance.service.binance_svc import BinanceSvc

if __name__ == '__main__':
    binance_svc = BinanceSvc()
    kline_list = binance_svc.get_historical_klines(BinanceProduct.BTCUSDT, Client.KLINE_INTERVAL_1DAY,
                                             datetime.now() - relativedelta(**{"weeks": 2}), datetime.now())
    volatility_list = []
    for kline in kline_list:
        volatility_list.append(kline.high - kline.low)

    std = np.std(volatility_list, ddof=1)
    mean = sum(volatility_list) / len(volatility_list)
    print(f"{mean-std} ~ {mean} ~ {mean+std}")