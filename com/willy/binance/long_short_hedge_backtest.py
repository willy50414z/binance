from decimal import Decimal

import numpy as np
from binance import Client
from dateutil.relativedelta import relativedelta

from com.willy.binance.dto.hedge_grid_backtest_req import HedgeGridBacktestReq
from com.willy.binance.enums.binance_product import BinanceProduct
from com.willy.binance.service.binance_svc import BinanceSvc
from com.willy.binance.util import type_util

if __name__ == '__main__':
    start_datetime = type_util.str_to_datetime("2025-10-08T00:00:00Z")
    # 撈出前一筆收盤價
    binance_svc = BinanceSvc()
    klines = binance_svc.get_historical_klines(BinanceProduct.BTCUSDT, Client.KLINE_INTERVAL_5MINUTE,
                                               start_datetime - relativedelta(**{"minutes": 5}), start_datetime)

    last_close = None
    for kline in klines:
        if kline.start_time == start_datetime:
            last_close = kline.open

    if not last_close:
        raise ValueError("can't get last_close")

    # 計算網格區間
    kline_list = binance_svc.get_historical_klines(BinanceProduct.BTCUSDT, Client.KLINE_INTERVAL_1DAY,
                                                   start_datetime - relativedelta(**{"weeks": 2}), start_datetime)

    volatility_list = []
    for kline in kline_list:
        volatility_list.append(kline.high - kline.low)
    std = int(np.std(volatility_list, ddof=1))

    invest_amt = Decimal(1000)
    leverage_ratio_str = Decimal(100)
    level_amt_change = "150%"
    binance_svc.backtest_hedge_grid_list([HedgeGridBacktestReq("std_calc_grid_strategy", BinanceProduct.BTCUSDT,
                                                               Client.KLINE_INTERVAL_8HOUR, int(last_close) - std,
                                                               int(last_close) + std, "20", start_datetime,
                                                               start_datetime + relativedelta(**{"days": 3}),
                                                               invest_amt, level_amt_change, leverage_ratio_str)])
