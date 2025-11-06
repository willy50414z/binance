import datetime
import logging
import math
from datetime import timezone
from decimal import Decimal

from binance import Client

from com.willy.binance.config.config_util import config_util
from com.willy.binance.dto.binance_kline import BinanceKline
from com.willy.binance.dto.hedge_trade_price_amt import HedgeTradePriceAmt
from com.willy.binance.enum import trade_type
from com.willy.binance.enum.binance_product import BinanceProduct
from com.willy.binance.enum.handle_fee_type import HandleFeeType
from com.willy.binance.enum.trade_type import TradeType
from com.willy.binance.service import trade_svc
from com.willy.binance.util import type_util


def calc_first_layer_invest_amt(total_invest_amt: int, level_gap: float, levels: int):
    single_side_invest_amt = total_invest_amt / 2
    if levels <= 0:
        return 0.0
    if level_gap == 1:
        return single_side_invest_amt / levels
    return round(single_side_invest_amt * (1 - level_gap) / (1 - level_gap ** levels))


class BinanceSvc:
    config = config_util("binance.acct.hedgebuy")
    client = Client(config.get("apikey"), config.get("privatekey"))

    def get_historical_klines(self, binance_product: BinanceProduct, kline_interval=Client.KLINE_INTERVAL_1DAY,
                              start_date: datetime = type_util.str_to_datetime("20250101"),
                              end_date: datetime = type_util.str_to_datetime("20250105")):
        klines = self.client.get_historical_klines(binance_product.name, kline_interval,
                                                   int(start_date.timestamp() * 1000),
                                                   int(end_date.timestamp() * 1000))
        kline_list = []
        for kline in klines:
            kline_list.append(
                BinanceKline(start_time=type_util.timestamp_to_datetime(kline[0] // 1000, tz=timezone.utc),
                             open=Decimal(kline[1]),
                             high=Decimal(kline[2]), low=Decimal(kline[3]), close=Decimal(kline[4]),
                             vol=Decimal(kline[5]),
                             end_time=type_util.timestamp_to_datetime(kline[6] // 1000, tz=timezone.utc),
                             number_of_trade=kline[8]))
        return kline_list

    def backtest_hedge_grid(self, binance_product: BinanceProduct, lower_bound: int, upper_bound: int, grid_levels: str,
                            start_time: datetime.datetime, end_time: datetime.datetime, invest_amt: int,
                            level_amt_change: str, leverage_ratio: Decimal):
        """
        回測買賣對沖策略損益

        :param binance_product:
        :param lower_bound:
        :param upper_bound:
        :param grid_levels:
        網格劃分數量
        可以是'10'表示劃分成10格做交易
        也可以是'5%'表示每5%為一格
        :param start_time:
        :param end_time:
        :param invest_amt:
        :param level_amt_change:
        每網格，投資金額調整多少
        可以是'500'表示每一網格投資金額差距為500
        也可以是'5%'表示每一網格投資金額差距為5%
        :param leverage_ratio:
        :return:
        """

        # print出回測資訊
        logging.info(
            f"product[{binance_product}]start_time[{type_util.datetime_to_str(start_time)}]end_time[{type_util.datetime_to_str(end_time)}]")
        logging.info(
            f"price range[{lower_bound} - {upper_bound}]grid_levels[{grid_levels}]invest_amt[{invest_amt}]level_amt_change[{level_amt_change}]leverage_ratio[{leverage_ratio}]")

        # 計算買賣策略
        ## 計算網格價格
        trade_price = upper_bound
        trade_price_list = []
        if grid_levels.endswith("%"):
            grid_gap_ratio = int(grid_levels[0:len(grid_levels) - 1])
            while trade_price >= lower_bound:
                # hedge_trade_price_amt_list.append(HedgeTradePriceAmt(price=trade_price, buy_amt=))
                trade_price = trade_price * (1 - grid_gap_ratio / 100)
            raise ValueError("grid_levels end with % is not implement")
        else:
            grid_gap = (upper_bound - lower_bound) // int(grid_levels)
            while trade_price >= lower_bound:
                trade_price_list.append(trade_price)
                trade_price -= grid_gap

        # 計算第一層投入金額
        invest_amt_list = []
        first_layer_invest_amt = 0
        if level_amt_change.endswith("%"):
            level_change_percent = float(level_amt_change[:len(level_amt_change) - 1])
            first_layer_invest_amt = calc_first_layer_invest_amt(invest_amt * leverage_ratio, level_change_percent,
                                                                 len(trade_price_list))
            last_layer_invest_amt = first_layer_invest_amt
            for i in range(len(trade_price_list)):
                invest_amt_list.append(Decimal(last_layer_invest_amt))
                last_layer_invest_amt = math.floor(last_layer_invest_amt * level_change_percent)
        else:
            raise ValueError(f"level_amt_change should end with '%' but level_amt_change[{level_amt_change}]")

        ## 印出網格投資表
        hedge_trade_price_amt_list = []
        for i in range(len(trade_price_list)):
            hedge_trade_price_amt_list.append(
                HedgeTradePriceAmt(Decimal(trade_price_list[i]), invest_amt_list[len(trade_price_list) - i - 1],
                                   invest_amt_list[i], False))

        logging.info("      \tbuy amt\tsell amt")
        for hedge_trade_price_amt in hedge_trade_price_amt_list:
            logging.info(
                f"{hedge_trade_price_amt.price}\t{hedge_trade_price_amt.buy_amt}\t{hedge_trade_price_amt.sellAmt}")

        daily_kline_list = self.get_historical_klines(binance_product, start_date=start_time, end_date=end_time)

        buy_acct_trade_record = []
        sell_acct_trade_record = []
        for daily_kline in daily_kline_list:
            # 逐日確定是否觸發交易
            logging.info(daily_kline)
            for hedge_trade_price_amt in hedge_trade_price_amt_list:
                if not hedge_trade_price_amt.has_trade and daily_kline.high > hedge_trade_price_amt.price and daily_kline.low < hedge_trade_price_amt.price:
                    # five_minutes_kline_list = self.get_historical_klines(binance_product, Client.KLINE_INTERVAL_5MINUTE, start_date=daily_kline.start_time, end_date=daily_kline.end_time)
                    # 觸發交易時紀錄交易紀錄
                    trade_record = trade_svc.create_trade_record(daily_kline.start_time, TradeType.BUY,
                                                                 hedge_trade_price_amt.price,
                                                                 hedge_trade_price_amt.buy_amt, HandleFeeType.MAKER);

                    trade_record = trade_svc.create_trade_record(daily_kline.start_time, TradeType.SELL,
                                                                 hedge_trade_price_amt.price,
                                                                 hedge_trade_price_amt.sellAmt, HandleFeeType.MAKER)

                    if trade_record:
                        buy_acct_trade_record.append(trade_record)

                    if trade_record:
                        sell_acct_trade_record.append(trade_record)

        if len(buy_acct_trade_record) > 0:
            logging.info(
                trade_svc.build_trade_detail_list(daily_kline_list[len(daily_kline_list) - 1].close, Decimal(invest_amt),
                                                  leverage_ratio,
                                                  buy_acct_trade_record,
                                                  daily_kline_list[len(daily_kline_list) - 1].end_time))

        if len(sell_acct_trade_record) > 0:
            logging.info(
                trade_svc.build_trade_detail_list(daily_kline_list[len(daily_kline_list) - 1].close, Decimal(invest_amt),
                                                  leverage_ratio,
                                                  sell_acct_trade_record,
                                                  daily_kline_list[len(daily_kline_list) - 1].end_time))


def calc_current_price(y, avg_price, total_amt):
    """
    根據損益反推現價
    :param y: 損益 (USDT)
    :param avg_price: 開倉均價
    :param total_amt: 倉位金額 (USDT)
    :return: 現價 (current_price)
    """
    current_price = (avg_price * (1 + y / total_amt)) / 0.9996
    return current_price


if __name__ == '__main__':
    # print(calc_current_price(-203619.2, 103471.35, 203619.2))
    # print(calc_profit(101101.9, 103471.35, 203619.2))
    # print(calc_first_layer_invest_amt(1625, 1.5, 4))
    BinanceSvc().backtest_hedge_grid(BinanceProduct.BTCUSDT, 100000, 120000, "20",
                                     type_util.str_to_datetime("20250101"), type_util.str_to_datetime("20251201"),
                                     8000, "1.5%", 60)
