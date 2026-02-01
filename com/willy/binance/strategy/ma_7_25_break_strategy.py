import logging
from datetime import datetime
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
            logging.debug("[strategy]meet trade_twice at same side, will stop trading")
            # 上一次是同向交易 => 直接平倉 因為同向交易發生時，大多會虧損
            return trade_svc.create_close_trade_record(now_trade_record.date,
                                                       now_trade_record.price, last_td,
                                                       reason=TradeReason(
                                                           TradeReasonType.PASSIVE,
                                                           "同向交易攤平"))

    return now_trade_record


class Ma725BreakIndexSwitch(IndexSwitch):
    RSI = 1
    # ADX = 2
    ATR = 3
    KEEP = 4
    FAKE_BREAK = 5
    TIME_FILTER = 6
    # FAKE_BREAK_EARN = 6
    # FAKE_BREAK_RSI = 7


class Ma725BreakStrategy(TradingStrategy):
    def is_meet_tech_idx_with_switch(self, row) -> bool:
        if self.get_trade_index_switch_status(Ma725BreakIndexSwitch.KEEP):
            if row.ma7 < row.ma25 and row.is_ma25_keep_grow:
                logging.debug(f"[is_meet_tech_idx_with_switch] fail in KEEP grow")
                return False
            if row.ma7 > row.ma25 and row.is_ma25_keep_fall:
                logging.debug(f"[is_meet_tech_idx_with_switch] fail in KEEP fall")
                return False

        if self.get_trade_index_switch_status(Ma725BreakIndexSwitch.RSI):
            # if row.ma7 < row.ma25 and row.rsi < 30:
            #     return False
            if row.ma7 > row.ma25 and row.rsi < 60:
                logging.debug(f"[is_meet_tech_idx_with_switch] fail in rsi fall")
                return False

            # ADX 過濾：開關打開且趨勢太弱 (ADX < 25) 時攔截
        # if self.get_trade_index_switch_status(MaIndexSwitch.ADX):
        #     if row.adx < 25:
        #         return False

        # MA25 趨勢過濾：開關打開且 MA25 沒有持續增長時攔截
        if self.get_trade_index_switch_status(Ma725BreakIndexSwitch.ATR):
            if row.atr < (row.atr_mean * 0.8):
                logging.debug(f"[is_meet_tech_idx_with_switch] fail in ATR")
                return False

        if self.get_trade_index_switch_status(Ma725BreakIndexSwitch.TIME_FILTER):
            logging.debug(f"[is_meet_tech_idx_with_switch] fail in TIME_FILTER")
            return self.is_trade_allowed_time(row.end_time)
        logging.debug(f"[is_meet_tech_idx_with_switch] check success")
        return True

    @property
    def lookback_ticks(self) -> int:
        return 100

    @property
    def tickets_interval(self) -> str:
        return Client.KLINE_INTERVAL_15MINUTE

    @property
    def tech_idx_list(self) -> List[TechIdxType]:
        return [TechIdxType.SMA_7, TechIdxType.SMA_25, TechIdxType.IS_MA25_KEEP_GROW,
                TechIdxType.IS_MA25_KEEP_FALL, TechIdxType.MA7_AND_MA25_REL, TechIdxType.ADX_14, TechIdxType.ATR_14,
                TechIdxType.RSI_14]

    @property
    def strategy_idx_switches(self) -> Type[IndexSwitch]:
        return Ma725BreakIndexSwitch

    def get_invest_amt(self):
        if self.last_td is not None and self.last_td.acct_balance > 0:
            return self.last_td.acct_balance * Decimal("0.1") * self.leverage
        else:
            return self.initial_capital * Decimal("0.1") * self.leverage

    def get_trade_record_by_date(self, df: DataFrame) -> None | TradeRecord:
        lastest_row = df.iloc[-1]

        trade_record = self.trade_if_cross_ma(self.last_td, lastest_row)
        if trade_record:
            logging.debug("[strategy] trade in trade_if_cross_ma")
            return trade_record

        # 3. 獲利時，MA7/MA25連續3期逐漸變小且<100點 => 停利
        trade_record = self.get_stop_loss_trade_record(self.last_td, lastest_row)
        if trade_record:
            logging.debug("[strategy] trade in stop_loss_trade")
            return trade_record

        # 如果是假突破或假跌破(5K內又跌/漲回去)，把買/賣的賣/買回來
        if self.get_trade_index_switch_status(Ma725BreakIndexSwitch.FAKE_BREAK):
            trade_record = self.fake_break(lastest_row)
            if trade_record:
                logging.debug("[strategy] trade in fake_break")
                return trade_record

        return None

    def is_trade_allowed_time(self, current_time: datetime) -> bool:
        """
        過濾掉 22:00 到 01:00 之間的交易訊號
        """
        # 取得小時與分鐘
        hour = current_time.hour
        minute = current_time.minute

        # 舉例：禁止 22:00 ~ 01:00 (包含 22:15, 00:45)
        # 注意：這裡的時間通常是 UTC，請根據你的 K 線時區調整
        forbidden_hours = [22, 23, 0]

        if hour in forbidden_hours:
            return False

        return True

    def trade_if_cross_ma(self, last_td, row):
        # 1. MA7 / MA25 超過20期沒有交叉 > 交叉後確立做多/空方向
        ma7_and_ma25_rel_criteria = 20
        if abs(row.last_ma7_and_ma25_rel) >= ma7_and_ma25_rel_criteria:
            if row.last_ma7_and_ma25_rel > 0:
                # ma7在ma25上面持續超過20期
                if row.ma7 < row.ma25 and self.is_meet_tech_idx_with_switch(row):
                    # ma7如果跌破ma25的時候賣
                    # # 如果之前做空，現在也做空，價差至少要>1000
                    # if last_td and last_td.trade_record.type == TradeType.SELL and abs(
                    #         last_td.trade_record.price - Decimal(row.ma7)) < 1000:
                    #     continue

                    # 如果之前是做多，現在要改做空，所以sell amt要包含之前做多的一起平掉
                    if last_td is not None:
                        handle_unit = last_td.units
                    else:
                        handle_unit = Decimal("0")

                    trade_amt = self.get_invest_amt()
                    acct_handle_unit = handle_unit if handle_unit > 0 else Decimal("0")
                    trade_type = TradeType.SELL

                    unit = trade_svc.calc_buyable_units(trade_amt, row.close) + acct_handle_unit
                    now_trade_record = trade_svc.create_trade_record(row.start_time, trade_type, row.close,
                                                                     unit=unit, handle_fee_type=HandleFeeType.TAKER,
                                                                     reason=TradeReason(TradeReasonType.ACTIVE,
                                                                                        "符合條件"))

                    # 6. 連續2次符合條件且方向相同，直接平倉
                    return trade_if_not_trade_twice(now_trade_record, last_td)
            elif row.last_ma7_and_ma25_rel < 0 and self.is_meet_tech_idx_with_switch(row):
                if row.ma7 > row.ma25:
                    # ma7如果突破ma25的時候買
                    # # 如果之前做多，現在也做多，價差至少要>1000
                    # if last_td and last_td.trade_record.type == TradeType.BUY and abs(
                    #         last_td.trade_record.price - Decimal(row.ma7)) < 1000:
                    #     continue

                    # 如果之前是做空，現在要改做多，所以buy amt要包含之前做多的一起平掉
                    if last_td is not None:
                        handle_unit = last_td.units
                    else:
                        handle_unit = Decimal("0")

                    trade_amt = self.get_invest_amt()
                    acct_handle_unit = handle_unit if handle_unit < 0 else Decimal("0")
                    trade_type = TradeType.BUY

                    unit = trade_svc.calc_buyable_units(trade_amt, row.close) - acct_handle_unit
                    now_trade_record = trade_svc.create_trade_record(row.start_time, trade_type, row.close,
                                                                     unit=unit, handle_fee_type=HandleFeeType.TAKER,
                                                                     reason=TradeReason(TradeReasonType.ACTIVE,
                                                                                        "符合條件"))

                    # 6. 連續2次符合條件且方向相同，直接平倉
                    return trade_if_not_trade_twice(now_trade_record, last_td)
        else:
            logging.debug(
                f"[strategy]ma7 and ma25 diff is less than {ma7_and_ma25_rel_criteria}, abs(row.last_ma7_and_ma25_rel)[{abs(row.last_ma7_and_ma25_rel)}]")

    def get_stop_loss_trade_record(self, last_td, row):
        if last_td:
            unrealize_profit = trade_svc.calc_profit(Decimal(str(row.close)), last_td.handle_amt, last_td.handling_fee,
                                                     last_td.units)
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
                # 做多
                if last_td.units > 0 and (last_td.handle_amt / last_td.units - Decimal(str(row.low))) > 1000:
                    logging.debug("[strategy]stop loss")
                    return trade_svc.create_close_trade_record(row.start_time, round(
                        last_td.handle_amt / last_td.units, 2) - 1000, last_td,
                                                               reason=TradeReason(
                                                                   TradeReasonType.PASSIVE,
                                                                   "停損"))

                # 做空
                if last_td.units < 0 and (Decimal(str(row.high)) + last_td.handle_amt / last_td.units) > 1000:
                    logging.debug("[strategy]stop loss")
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

            # if self.get_trade_index_switch_status(MaIndexSwitch.FAKE_BREAK_EARN) and last_1_td.profit > 0:
            #     return None

            # 近2個交易是做反向交易
            # 賣>買>馬上跌破 > 賣
            # 買>賣>馬上突破 > 買
            if last_1_td.trade_record.type != last_2_td.trade_record.type \
                    and ((last_1_td.trade_record.type == TradeType.BUY and row.ma7 < row.ma25 and (
                    self.date_idx_map[row.start_time] - self.date_idx_map[last_1_td.trade_record.date]) < 5) \
                         or (last_1_td.trade_record.type == TradeType.SELL and row.ma7 > row.ma25 and (
                            self.date_idx_map[row.start_time] - self.date_idx_map[last_1_td.trade_record.date]) < 5)):
                # build trade record
                trade_type = TradeType.BUY if last_1_td.trade_record.type == TradeType.SELL else TradeType.SELL

                # if self.get_trade_index_switch_status(MaIndexSwitch.FAKE_BREAK_RSI):
                #     if (row.rsi > 80 and trade_type == TradeType.BUY) or (
                #             row.rsi < 20 and trade_type == TradeType.SELL):
                #         return None

                unit = abs(last_2_td.units) if last_1_td.units == 0 else abs(last_2_td.units) + abs(last_1_td.units)

                touch_ma_trade_record = trade_svc.create_trade_record(row.start_time, trade_type,
                                                                      row.close,
                                                                      unit=unit,
                                                                      handle_fee_type=HandleFeeType.TAKER,
                                                                      reason=TradeReason(
                                                                          TradeReasonType.ACTIVE,
                                                                          "假突跌破，認錯回補"))
                return touch_ma_trade_record
