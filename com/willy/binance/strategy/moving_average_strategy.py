from decimal import Decimal
from typing import List, Type

from binance import Client
from pandas import DataFrame

from com.willy.binance.dto.trade_record import TradeRecord
from com.willy.binance.enums.handle_fee_type import HandleFeeType
from com.willy.binance.enums.tech_idx_type import TechIdxType
from com.willy.binance.enums.trade_reason import TradeReason, TradeReasonType
from com.willy.binance.enums.trade_type import TradeType
from com.willy.binance.service import trade_svc
from com.willy.binance.strategy.trade_strategy import TradingStrategy, IndexSwitch


def trade_if_not_trade_twice(now_trade_record, last_td):
    if now_trade_record:
        if last_td is not None and last_td.trade_record.type == now_trade_record.type and last_td.units != 0:
            # 上一次是同向交易 => 直接平倉 因為同向交易發生時，大多會虧損
            return trade_svc.create_close_trade_record(now_trade_record.date,
                                                       now_trade_record.price, last_td,
                                                       reason=TradeReason(
                                                           TradeReasonType.PASSIVE,
                                                           "同向交易攤平"))

    return now_trade_record


class MaIndexSwitch(IndexSwitch):
    RSI = 1
    ADX = 2
    ATR = 3
    KEEP = 4


class MovingAverageStrategy(TradingStrategy):
    invest_amt = 0
    guarantee_amt = 0

    @property
    def invest_and_guarantee_ratio(self) -> float:
        return 0.25

    @property
    def lookback_ticks(self) -> int:
        return 100

    @property
    def tickets_interval(self) -> str:
        return Client.KLINE_INTERVAL_15MINUTE

    @property
    def tech_idx_list(self) -> List[TechIdxType]:
        return [TechIdxType.SMA_7, TechIdxType.SMA_25, TechIdxType.IS_MA25_KEEP_GROW_20,
                TechIdxType.IS_MA25_KEEP_FALL_20, TechIdxType.MA7_AND_MA25_REL, TechIdxType.ADX_14, TechIdxType.ATR_14,
                TechIdxType.RSI_14]

    @property
    def strategy_idx_switches(self) -> Type[IndexSwitch]:
        return MaIndexSwitch

    def get_trade_record_by_date(self, df: DataFrame) -> None | TradeRecord:
        current_row = df.iloc[-1]

        trade_record = self.trade_if_cross_ma(self.last_td, current_row)
        if trade_record:
            return trade_record

        # 3. 獲利時，MA7/MA25連續3期逐漸變小且<100點 => 停利
        trade_record = self.get_stop_loss_trade_record(self.last_td, current_row)
        if trade_record:
            return trade_record

        # 如果是假突破或假跌破(5K內又跌/漲回去)，把買/賣的賣/買回來
        trade_record = self.fake_break(current_row)
        if trade_record:
            return trade_record

        return None

    def close_position_if_ma25_back(self, last_td, row):
        if last_td:
            if last_td.units > 0 and row.is_ma25_keep_fall_20:
                return trade_svc.create_trade_record(row.start_time, TradeType.SELL, Decimal(row.open),
                                                     unit=last_td.units, handle_fee_type=HandleFeeType.TAKER,
                                                     reason=TradeReason(TradeReasonType.ACTIVE,
                                                                        "做多停利"))
            elif last_td.units < 0 and row.is_ma25_keep_grow_20:
                return trade_svc.create_trade_record(row.start_time, TradeType.BUY, Decimal(row.open),
                                                     unit=last_td.units, handle_fee_type=HandleFeeType.TAKER,
                                                     reason=TradeReason(TradeReasonType.ACTIVE,
                                                                        "放空停利"))
        return None

    def trade_if_cross_ma(self, last_td, row):
        # 1. MA7 / MA25 超過20期沒有交叉 > 交叉後確立做多/空方向
        if abs(row.last_ma7_and_ma25_rel) >= 20:
            if row.last_ma7_and_ma25_rel > 0:
                # ma7在ma25上面持續超過20期
                if row.ma7 < row.ma25 and not row.is_ma25_keep_grow_20:
                    # ma7如果跌破ma25的時候賣
                    # # 如果之前做空，現在也做空，價差至少要>1000
                    # if last_td and last_td.trade_record.type == TradeType.SELL and abs(
                    #         last_td.trade_record.price - Decimal(row.ma7)) < 1000:
                    #     continue

                    # 如果之前是做多，現在要改做空，所以sell amt要包含之前做多的一起平掉
                    if last_td is not None:
                        handle_unit = last_td.units
                    else:
                        handle_unit = Decimal(0)

                    trade_amt = Decimal(self.get_single_invest_amt())
                    acct_handle_unit = handle_unit if handle_unit > 0 else Decimal(0)
                    trade_type = TradeType.SELL

                    unit = trade_svc.calc_buyable_units(trade_amt, Decimal(row.close)) + acct_handle_unit
                    now_trade_record = trade_svc.create_trade_record(row.start_time, trade_type, Decimal(row.close),
                                                                     unit=unit, handle_fee_type=HandleFeeType.TAKER,
                                                                     reason=TradeReason(TradeReasonType.ACTIVE,
                                                                                        "符合條件"))

                    # 6. 連續2次符合條件且方向相同，直接平倉
                    return trade_if_not_trade_twice(now_trade_record, last_td)
            elif row.last_ma7_and_ma25_rel < 0:
                if row.ma7 > row.ma25 and not row.is_ma25_keep_fall_20:
                    # ma7如果突破ma25的時候買
                    # # 如果之前做多，現在也做多，價差至少要>1000
                    # if last_td and last_td.trade_record.type == TradeType.BUY and abs(
                    #         last_td.trade_record.price - Decimal(row.ma7)) < 1000:
                    #     continue

                    # 如果之前是做空，現在要改做多，所以buy amt要包含之前做多的一起平掉
                    if last_td is not None:
                        handle_unit = last_td.units
                    else:
                        handle_unit = Decimal(0)

                    trade_amt = Decimal(self.get_single_invest_amt())
                    acct_handle_unit = handle_unit if handle_unit < 0 else Decimal(0)
                    trade_type = TradeType.BUY

                    unit = trade_svc.calc_buyable_units(trade_amt, Decimal(row.close)) - acct_handle_unit
                    now_trade_record = trade_svc.create_trade_record(row.start_time, trade_type, Decimal(row.close),
                                                                     unit=unit, handle_fee_type=HandleFeeType.TAKER,
                                                                     reason=TradeReason(TradeReasonType.ACTIVE,
                                                                                        "符合條件"))

                    # 6. 連續2次符合條件且方向相同，直接平倉
                    return trade_if_not_trade_twice(now_trade_record, last_td)

    def get_stop_loss_trade_record(self, last_td, row):
        if last_td:
            unrealize_profit = trade_svc.calc_profit(row.close, last_td.handle_amt, last_td.handling_fee, last_td.units)
            if unrealize_profit and unrealize_profit > 0:
                is_need_close = False
                # if abs(df.iloc[i - 2].ma7 - df.iloc[i - 2].ma25) > abs(df.iloc[i - 1].ma7 - df.iloc[i - 1].ma25) > abs(
                #         df.iloc[i].ma7 - df.iloc[i].ma25) < 100:
                #     is_need_close = True
                #
                # if is_need_close:
                #     trade_svc.build_txn_detail_list_df(row,
                #                                        invest_amt,
                #                                        guarantee_amt,
                #                                        ma_dca_backtest_req.leverage_ratio,
                #                                        trade_svc.create_close_trade_record(row.start_time, row.close,
                #                                                                            last_td, reason="停利"),
                #                                        trade_detail)
                #     reset_available_trade_amt(trade_level_list)
            elif unrealize_profit and unrealize_profit < 0:
                # 5. 虧損超過1000點 => 停損
                if last_td.units > 0 and (last_td.handle_amt / last_td.units - Decimal(row.low)) > 1000:
                    return trade_svc.create_close_trade_record(row.start_time, round(
                        last_td.handle_amt / last_td.units, 2) - 1000, last_td,
                                                               reason=TradeReason(
                                                                   TradeReasonType.PASSIVE,
                                                                   "停損"))
                if last_td.units < 0 and (Decimal(row.high) + last_td.handle_amt / last_td.units) > 1000:
                    return trade_svc.create_close_trade_record(row.start_time, round(
                        last_td.handle_amt / last_td.units * -1, 2) + 1000, last_td,
                                                               reason=TradeReason(
                                                                   TradeReasonType.PASSIVE,
                                                                   "停損"))

    def fake_break(self, row):
        if len(self.trade_detail.txn_detail_list) > 1:
            non_stop_loss_td_list = [td for td in self.trade_detail.txn_detail_list if
                                     td.trade_record.reason.trade_reason_type != TradeReasonType.PASSIVE]
            last_1_td = non_stop_loss_td_list[len(non_stop_loss_td_list) - 1]
            last_2_td = non_stop_loss_td_list[len(non_stop_loss_td_list) - 2]

            # last_1_td = trade_detail.txn_detail_list[len(trade_detail.txn_detail_list) - 1]
            # last_2_td = trade_detail.txn_detail_list[len(trade_detail.txn_detail_list) - 2]
            # 近2個交易是做反向交易
            # 賣>買>馬上跌破 > 賣
            # 買>賣>馬上突破 > 買
            if last_1_td.trade_record.type != last_2_td.trade_record.type \
                    and ((last_1_td.trade_record.type == TradeType.BUY and row.ma7 < row.ma25 and (
                    self.date_idx_map[row.start_time] - self.date_idx_map[last_1_td.trade_record.date]) < 10) \
                         or (last_1_td.trade_record.type == TradeType.SELL and row.ma7 > row.ma25 and (
                            self.date_idx_map[row.start_time] - self.date_idx_map[last_1_td.trade_record.date]) < 10)):
                # build trade record
                trade_type = TradeType.BUY if last_1_td.trade_record.type == TradeType.SELL else TradeType.SELL
                touch_ma_trade_record = trade_svc.create_trade_record(row.start_time, trade_type,
                                                                      Decimal(row.close),
                                                                      unit=abs(last_2_td.units) + abs(last_1_td.units),
                                                                      handle_fee_type=HandleFeeType.TAKER,
                                                                      reason=TradeReason(
                                                                          TradeReasonType.ACTIVE,
                                                                          "假突跌破，認錯回補"))
                return touch_ma_trade_record
