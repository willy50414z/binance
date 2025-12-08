from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from decimal import Decimal

import pandas as pd

from com.willy.binance.dto.trade_detail import TradeDetail
from com.willy.binance.dto.trade_record import TradeRecord
from com.willy.binance.enums.binance_product import BinanceProduct
from com.willy.binance.enums.trade_reason import TradeReason, TradeReasonType
from com.willy.binance.service import trade_svc, chart_service
from com.willy.binance.service.binance_svc import BinanceSvc
from com.willy.binance.util import type_util


class TradingStrategy(ABC):
    def __init__(self, test_name, start_time: datetime,
                 end_time: datetime,
                 initial_capital: int,
                 product: BinanceProduct,
                 leverage: int, other_args: dict):
        self.test_name = test_name
        self.start_time = start_time
        self.end_time = end_time
        self.initial_capital = initial_capital
        self.product = product
        self.leverage = leverage
        self.other_args = other_args
        self.invest_amt = round(float(self.invest_and_guarantee_ratio * initial_capital), 2)
        self.guarantee_amt = initial_capital - self.invest_amt
        self.binance_svc = BinanceSvc()
        self.trade_detail = TradeDetail(False, False, [])
        self.date_idx_map = {}

    def get_single_invest_amt(self, last_td):
        if last_td:
            return min(self.invest_amt, int(last_td.acct_balance))
        else:
            return self.invest_amt

    def get_lookback_timedelta(self) -> timedelta:
        if self.tickets_interval.endswith("m"):
            return timedelta(
                minutes=float(self.tickets_interval[:len(self.tickets_interval) - 1]) * self.lookback_tickets)
        elif self.tickets_interval.endswith("h"):
            return timedelta(
                hours=float(self.tickets_interval[:len(self.tickets_interval) - 1]) * self.lookback_tickets)
        elif self.tickets_interval.endswith("d"):
            return timedelta(
                days=float(self.tickets_interval[:len(self.tickets_interval) - 1]) * self.lookback_tickets)
        elif self.tickets_interval.endswith("w"):
            return timedelta(
                weeks=float(self.tickets_interval[:len(self.tickets_interval) - 1]) * self.lookback_tickets)
        else:
            raise ValueError(f"unexpect time unit[{self.tickets_interval}]")

    @property
    @abstractmethod
    def lookback_tickets(self) -> int:
        pass

    @property
    @abstractmethod
    def tickets_interval(self) -> str:
        pass

    @property
    @abstractmethod
    def invest_and_guarantee_ratio(self) -> float:
        pass

    @abstractmethod
    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        [強制實現] 接收原始歷史數據，計算指標 (如 MA, RSI) 並返回。
        """
        pass

    @abstractmethod
    def get_trade_record_by_date(self, dt: datetime) -> TradeRecord:
        """

        """
        pass

    @abstractmethod
    def build_chart_dataframe(self, history_dataframe):
        pass

    # @abstractmethod
    # def get_trade_record(self, row: pd.Series, trade_detail: TradeDetail) -> TradeRecord:
    #     """
    #     [強制實現] 根據當前數據和持倉，決定當日的交易量和原因。
    #
    #     Args:
    #         trade_detail:
    #         row: 當前日期的數據 (包含指標)。
    #
    #     Returns:
    #         tuple: (units_change, reason)
    #                units_change > 0 買入, units_change < 0 賣出, units_change = 0 不操作
    #     """
    #     pass

    def check_break_position(self, row):
        # 確認有沒有爆倉
        last_td = self.trade_detail.txn_detail_list[len(self.trade_detail.txn_detail_list) - 1] if len(
            self.trade_detail.txn_detail_list) > 0 else None
        if last_td and ((last_td.units > 0 and Decimal(row.low) < last_td.force_close_offset_price) or (
                last_td.units < 0 and Decimal(row.high) > last_td.force_close_offset_price)):
            trade_svc.build_txn_detail_list_df(row,
                                               self.invest_amt,
                                               self.guarantee_amt,
                                               self.leverage,
                                               trade_svc.create_close_trade_record(row.start_time,
                                                                                   last_td.force_close_offset_price,
                                                                                   last_td,
                                                                                   reason=TradeReason(
                                                                                       TradeReasonType.PASSIVE,
                                                                                       "爆倉")),
                                               self.trade_detail)

    def run_backtest(self):
        # 獲取回測時間
        history_dataframe = \
            self.binance_svc.get_historical_klines_df(self.product, self.tickets_interval, self.start_time,
                                                      self.end_time)

        backtest_start_time_list = history_dataframe['start_time']
        row_idx = 0
        # 逐日回測
        for start_time in backtest_start_time_list:
            # 準備共用參數
            self.date_idx_map[start_time] = row_idx
            row_idx += 1
            if row_idx % 1000 == 0:
                print(f"finish {row_idx} / {backtest_start_time_list.shape[0]}")

            # 決策是否交易
            trade_record, df = self.get_trade_record_by_date(start_time)

            # 紀錄交易紀錄
            trade_svc.build_txn_detail_list_df(df.iloc[-1], self.invest_amt, self.guarantee_amt, self.leverage,
                                               trade_record,
                                               self.trade_detail)

            # 確認有沒有爆倉
            self.check_break_position(df.iloc[-1])

        # 製圖
        chart_dataframe = self.build_chart_dataframe(history_dataframe)
        chart_service.export_trade_point_chart(self.test_name, chart_dataframe, {
            "start_time": type_util.datetime_to_str(self.start_time, "%Y-%m-%d %H:%M:%S")
            , "end_time": type_util.datetime_to_str(self.end_time, "%Y-%m-%d %H:%M:%S")
            , "initial_capital": self.initial_capital
            , "product": self.product
            , "leverage": self.leverage
            , "other_args": self.other_args})
