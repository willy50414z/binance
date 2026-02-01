import logging
import math
from decimal import Decimal, ROUND_FLOOR
from typing import List

from binance import Client

from com.willy.binance.config.const import DECIMAL_PLACE_2
from com.willy.binance.dto.binance_kline import BinanceKline
from com.willy.binance.dto.fixed_price_invest_amt_dto import FixedPriceInvestAmtDto
from com.willy.binance.dto.hedge_grid_backtest_req import HedgeGridBacktestReq
from com.willy.binance.dto.hedge_grid_backtest_res import HedgeGridBacktestRes
from com.willy.binance.dto.trade_detail import TradeDetail
from com.willy.binance.enums.handle_fee_type import HandleFeeType
from com.willy.binance.enums.trade_type import TradeType
from com.willy.binance.service import trade_svc
from com.willy.binance.service.binance_svc import BinanceSvc
from com.willy.binance.util import type_util


def calc_first_layer_invest_amt(total_invest_amt: Decimal, level_gap: Decimal, levels: Decimal):
    single_side_invest_amt = total_invest_amt / 2
    if levels <= 0:
        return 0.0
    if level_gap == 1:
        return single_side_invest_amt / levels
    return round(single_side_invest_amt * (1 - level_gap) / (1 - level_gap ** levels))


class HedgeStrategy:
    enable_trade_detail_log = False
    enable_hedge_trade_plan_log = False
    enable_trade_summary_log = True

    def backtest_hedge_grid_list(self, hedge_grid_backtest_req_list: List[HedgeGridBacktestReq]):
        hedge_grid_backtest_res_list = []
        for hedge_grid_backtest_req in hedge_grid_backtest_req_list:
            hedge_grid_backtest_res_list.append(self.backtest_hedge_grid(hedge_grid_backtest_req))

        return hedge_grid_backtest_res_list

    def backtest_hedge_grid(self, hedge_grid_backtest_req: HedgeGridBacktestReq) -> HedgeGridBacktestRes:
        """

        Args:
            hedge_grid_backtest_req:

        Returns:

        """
        binance_svc = BinanceSvc()
        # print出回測資訊
        if self.enable_trade_summary_log:
            logging.info(
                f"product[{hedge_grid_backtest_req.binance_product}]start_time[{type_util.datetime_to_str(hedge_grid_backtest_req.start_time)}]end_time[{type_util.datetime_to_str(hedge_grid_backtest_req.end_time)}]")
            logging.info(
                f"price range[{hedge_grid_backtest_req.lower_bound} - {hedge_grid_backtest_req.upper_bound}]grid_levels[{hedge_grid_backtest_req.grid_levels}]invest_amt[{hedge_grid_backtest_req.invest_amt}]level_amt_change[{hedge_grid_backtest_req.level_amt_change}]leverage_ratio[{hedge_grid_backtest_req.leverage_ratio}]")

        # 計算買賣策略
        ## 計算網格價格
        trade_price = hedge_grid_backtest_req.upper_bound
        trade_price_list = []
        if hedge_grid_backtest_req.grid_levels.endswith("%"):
            grid_gap_ratio = Decimal(
                hedge_grid_backtest_req.grid_levels[0:len(hedge_grid_backtest_req.grid_levels) - 1])
            while trade_price >= hedge_grid_backtest_req.lower_bound:
                # hedge_trade_price_amt_list.append(HedgeTradePriceAmt(price=trade_price, buy_amt=))
                trade_price = trade_price * (1 - grid_gap_ratio / 100)
            raise ValueError("grid_levels end with % is not implement")
        else:
            grid_gap = (hedge_grid_backtest_req.upper_bound - hedge_grid_backtest_req.lower_bound) // int(
                hedge_grid_backtest_req.grid_levels)
            while trade_price >= hedge_grid_backtest_req.lower_bound:
                trade_price_list.append(trade_price)
                trade_price -= grid_gap

        # 計算第一層投入金額
        invest_amt_list = []
        first_layer_invest_amt = 0
        if hedge_grid_backtest_req.level_amt_change.endswith("%"):
            levels_amt_gap = Decimal(
                hedge_grid_backtest_req.level_amt_change[:len(hedge_grid_backtest_req.level_amt_change) - 1]) / 100
            first_layer_invest_amt = calc_first_layer_invest_amt(
                hedge_grid_backtest_req.invest_amt * hedge_grid_backtest_req.leverage_ratio,
                levels_amt_gap,
                Decimal(len(trade_price_list)))
            last_layer_invest_amt = first_layer_invest_amt
            for i in range(len(trade_price_list)):
                invest_amt_list.append(Decimal(last_layer_invest_amt))
                last_layer_invest_amt = math.floor(last_layer_invest_amt * levels_amt_gap)
        else:
            raise ValueError(
                f"level_amt_change should end with '%' but level_amt_change[{hedge_grid_backtest_req.level_amt_change}]")

        ## 印出網格投資表
        hedge_buy_list = []
        hedge_sell_list = []
        for i in range(len(trade_price_list)):
            hedge_buy_list.append(FixedPriceInvestAmtDto(False, Decimal(trade_price_list[i]), invest_amt_list[i]))
            hedge_sell_list.append(
                FixedPriceInvestAmtDto(False, Decimal(trade_price_list[i]),
                                       invest_amt_list[len(trade_price_list) - i - 1]))

        if self.enable_hedge_trade_plan_log:
            logging.info("      \tbuy amt\tsell amt")
            for hedge_trade_idx in range(len(hedge_buy_list)):
                logging.info(
                    f"{hedge_buy_list[hedge_trade_idx].price}\t{hedge_buy_list[hedge_trade_idx].amt}\t{hedge_sell_list[hedge_trade_idx].amt}")

        # 回測交易紀錄
        daily_kline_list = binance_svc.get_futures_historical_klines(hedge_grid_backtest_req.binance_product,
                                                                     Client.KLINE_INTERVAL_5MINUTE,
                                                                     start_date=hedge_grid_backtest_req.start_time,
                                                                     end_date=hedge_grid_backtest_req.end_time)
        single_side_invest_amt = (hedge_grid_backtest_req.invest_amt / 2).quantize(DECIMAL_PLACE_2, ROUND_FLOOR)
        single_side_guarantee_amt = (hedge_grid_backtest_req.guarantee_amt / 2).quantize(DECIMAL_PLACE_2, ROUND_FLOOR)

        # 回測買做多帳戶
        hedge_buy_trade_detail = self.get_trade_detail_list(TradeType.BUY,
                                                            single_side_invest_amt,
                                                            single_side_guarantee_amt,
                                                            hedge_grid_backtest_req.leverage_ratio,
                                                            daily_kline_list, hedge_buy_list)

        # 回測買做空帳戶
        hedge_sell_trade_detail = self.get_trade_detail_list(TradeType.SELL,
                                                             single_side_invest_amt,
                                                             single_side_guarantee_amt,
                                                             hedge_grid_backtest_req.leverage_ratio,
                                                             daily_kline_list, hedge_sell_list)

        self.log_out_hedge_trade_detail(hedge_buy_trade_detail.txn_detail_list, hedge_buy_trade_detail.txn_detail_list)
        #
        # if len(hedge_buy_trade_detail_list) == len(hedge_sell_trade_detail_list):
        #     for i in range(len(hedge_buy_trade_detail_list)):
        #         hedge_buy_trade_detail = hedge_buy_trade_detail_list[i]
        #         if hedge_buy_trade_detail.profit and hedge_sell_trade_detail_list[i].profit:
        #             print(
        #                 f"date[{hedge_buy_trade_detail.date}]current_price[{hedge_buy_trade_detail.current_price}]"
        #                 f"buy_profit[{hedge_buy_trade_detail.profit}]"
        #                 f"sell_profit[{hedge_sell_trade_detail_list[i].profit}]"
        #                 f"total_profit[{hedge_buy_trade_detail.profit + hedge_sell_trade_detail_list[i].profit}]")

        return HedgeGridBacktestRes(hedge_grid_backtest_req.name, hedge_buy_trade_detail, hedge_sell_trade_detail)

    def log_out_hedge_trade_detail(self, hedge_buy_trade_detail_list, hedge_sell_trade_detail_list):
        if self.enable_trade_detail_log:
            for i in range(len(hedge_buy_trade_detail_list)):
                if hedge_buy_trade_detail_list[i].trade_record or hedge_sell_trade_detail_list[i].trade_record:
                    logging.info(f"{hedge_buy_trade_detail_list[i]}\t{hedge_sell_trade_detail_list[i]}")

        # buy_acct_trade_record = []
        # sell_acct_trade_record = []
        # buy_trade_detail_list = []
        # sell_trade_detail_list = []
        # for daily_kline in daily_kline_list:
        #     # 逐日確定是否觸發交易
        #     # logging.info(daily_kline)
        #     for hedge_trade_price_amt in hedge_trade_price_amt_list:
        #         if not hedge_trade_price_amt.has_trade and daily_kline.high > hedge_trade_price_amt.price and daily_kline.low < hedge_trade_price_amt.price:
        #             # five_minutes_kline_list = self.get_historical_klines(binance_product, Client.KLINE_INTERVAL_5MINUTE, start_date=daily_kline.start_time, end_date=daily_kline.end_time)
        #             hedge_trade_price_amt.has_trade = True
        #
        #             # 觸發交易時紀錄交易紀錄
        #             trade_record = trade_svc.create_trade_record(daily_kline.start_time, TradeType.BUY,
        #                                                          hedge_trade_price_amt.price,
        #                                                          hedge_trade_price_amt.buy_amt, HandleFeeType.MAKER)
        #
        #             if trade_record:
        #                 buy_acct_trade_record.append(trade_record)
        #                 trade_svc.build_trade_detail_list(daily_kline.close,
        #                                                   Decimal(invest_amt),
        #                                                   leverage_ratio,
        #                                                   [trade_record],
        #                                                   daily_kline_list[len(daily_kline_list) - 1].end_time,
        #                                                   buy_trade_detail_list)
        #                 # print(buy_trade_detail_list[len(buy_trade_detail_list) - 1])
        #
        #             trade_record = trade_svc.create_trade_record(daily_kline.start_time, TradeType.SELL,
        #                                                          hedge_trade_price_amt.price,
        #                                                          hedge_trade_price_amt.sellAmt, HandleFeeType.MAKER)
        #
        #             if trade_record:
        #                 sell_acct_trade_record.append(trade_record)
        #                 trade_svc.build_trade_detail_list(daily_kline.close,
        #                                                   Decimal(invest_amt),
        #                                                   leverage_ratio,
        #                                                   [trade_record],
        #                                                   daily_kline_list[len(daily_kline_list) - 1].end_time,
        #                                                   sell_trade_detail_list)
        #                 # print(sell_trade_detail_list[len(sell_trade_detail_list) - 1])
        #
        # for buy_trade_detail in buy_trade_detail_list:
        #     print(buy_trade_detail)
        #
        # print("==============")
        #
        # for buy_trade_detail in sell_trade_detail_list:
        #     print(buy_trade_detail)

        # if len(buy_acct_trade_record) > 0:
        #     logging.info(
        #         trade_svc.build_trade_detail_list(daily_kline_list[len(daily_kline_list) - 1].close, Decimal(invest_amt),
        #                                           leverage_ratio,
        #                                           buy_acct_trade_record,
        #                                           daily_kline_list[len(daily_kline_list) - 1].end_time))
        #
        # if len(sell_acct_trade_record) > 0:
        #     logging.info(
        #         trade_svc.build_trade_detail_list(daily_kline_list[len(daily_kline_list) - 1].close, Decimal(invest_amt),
        #                                           leverage_ratio,
        #                                           sell_acct_trade_record,
        #                                           daily_kline_list[len(daily_kline_list) - 1].end_time))

    def get_trade_detail_list(self,
                              trade_type: TradeType,
                              invest_amt: Decimal,
                              guarantee_amt: Decimal,
                              leverage_ratio: Decimal,
                              kline_list: List[BinanceKline] = None,
                              trade_plan_list=None) -> TradeDetail:
        if trade_plan_list is None:
            trade_plan_list = []

        if kline_list is None:
            # kline_list = self.get_historical_klines(binance_product, start_date=start_time, end_date=end_time)
            raise ValueError(f"kline_list is None")

        trade_plan_price_list = [tp.price for tp in trade_plan_list]
        max_trade_plan_price = max(trade_plan_price_list)
        min_trade_plan_price = min(trade_plan_price_list)

        trade_detail = TradeDetail(False, False, [])
        for kline in kline_list:
            trade_record_list = []
            # 逐日確定是否觸發交易
            for trade_plan in trade_plan_list:
                if isinstance(trade_plan, FixedPriceInvestAmtDto):
                    # 確認網格是否被突破
                    if kline.high > max_trade_plan_price or kline.low < min_trade_plan_price:
                        trade_detail.is_grid_break = True
                    # 逐個價位檢查是否被觸發
                    if not trade_plan.is_traded and kline.high > trade_plan.price > kline.low:
                        # five_minutes_kline_list = self.get_historical_klines(binance_product, Client.KLINE_INTERVAL_5MINUTE, start_date=kline.start_time, end_date=kline.end_time)
                        trade_plan.is_traded = True

                        # 觸發交易時紀錄交易紀錄
                        trade_record = trade_svc.create_trade_record(kline.start_time, trade_type,
                                                                     trade_plan.price,
                                                                     amt=trade_plan.amt,
                                                                     handle_fee_type=HandleFeeType.MAKER)
                        if trade_record:
                            trade_record_list.append(trade_record)

            # 如果一個K棒觸發>2個交易區間 => 觸發融斷，結束交易，等到市場穩定
            # if len(trade_record_list) > 2:
            #     trade_detail.is_circuit_breaker = True
            #     # 將手上庫存都賣出
            #     total_handle_amt = Decimal(0)
            #     for trade_record in trade_record_list:
            #         total_handle_amt += trade_record.handle_amt
            #     total_handle_amt += trade_detail.txn_detail_list[len(trade_detail.txn_detail_list) - 1].handle_amt
            #     circuit_breaker_trade_type = TradeType.SELL if TradeType.BUY == trade_type else TradeType.BUY
            #     trade_record_list.append(trade_svc.create_trade_record(kline.end_time, circuit_breaker_trade_type,
            #                                                            kline.low,
            #                                                            total_handle_amt,
            #                                                            HandleFeeType.TAKER))

            if len(trade_record_list) > 0:
                for trade_record in trade_record_list:
                    trade_svc.build_txn_detail_list(kline,
                                                    invest_amt,
                                                    guarantee_amt,
                                                    leverage_ratio,
                                                    trade_record,
                                                    trade_detail)
                # 如果一個K棒觸發>2個交易區間 => 觸發融斷，結束交易，等到市場穩定
                if trade_detail.is_circuit_breaker:
                    return trade_detail
            else:
                trade_svc.build_txn_detail_list(kline,
                                                invest_amt,
                                                guarantee_amt,
                                                leverage_ratio,
                                                None,
                                                trade_detail)
            # 確認是否爆倉
            if trade_svc.check_is_force_close_offset(kline, invest_amt, guarantee_amt, leverage_ratio, trade_detail):
                break

        return trade_detail
