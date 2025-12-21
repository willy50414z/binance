import logging
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
        self.binance_svc = BinanceSvc(is_demo=False, is_testnet=False)
        self.trade_detail = TradeDetail(False, False, [])
        self.date_idx_map = {}

    def get_single_invest_amt(self, last_td):
        if last_td:
            return min(self.invest_amt, int(last_td.acct_balance)) * self.leverage
        else:
            return self.invest_amt * self.leverage

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

    def build_analysis_df(self, history_df):
        # 1. 將 txn_detail_list 轉成 DataFrame
        txn_data = []
        self.prepare_data(history_df)
        for td in self.trade_detail.txn_detail_list:
            txn_data.append({
                'start_time': td.date,
                'units': float(td.units),
                'current_price': float(td.current_price),
                'profit': float(td.profit),
                'profit_ratio': float(td.profit_ratio),
                'total_profit': float(td.total_profit),
                'acct_balance': float(td.acct_balance),
                'trade_type': td.trade_record.type.name,
                'trade_price': float(td.trade_record.price),
                'trade_reason': td.trade_record.reason.desc
            })

        if not txn_data:
            txn_df = pd.DataFrame(columns=[
                'start_time', 'units', 'current_price', 'profit',
                'profit_ratio', 'total_profit', 'acct_balance',
                'trade_type', 'trade_price', 'trade_reason'
            ])
        else:
            txn_df = pd.DataFrame(txn_data)

        if not txn_df.empty:
            txn_df.set_index('start_time', inplace=True)

        # 2. 與原始 history_df 合併 (history_df 包含了 MA, RSI, ADX 等指標)
        # 使用 left join，確保每一根 K 線都有資料，沒交易的地方會是 NaN
        return history_df.join(txn_df, how='left', rsuffix='_txn')

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
            # 帳戶餘額已歸零須停止回測
            if len(self.trade_detail.txn_detail_list) > 0:
                last_balance = self.trade_detail.txn_detail_list[-1].acct_balance
                if last_balance <= 0:
                    logging.info(f"[{start_time}] 帳戶餘額已歸零 ({last_balance})，終止回測。")
                    break

            # 準備共用參數
            self.date_idx_map[start_time] = row_idx
            row_idx += 1

            if row_idx % 1000 == 0:
                print(f"finish {row_idx} / {backtest_start_time_list.shape[0]}")

            # 確認有沒有爆倉
            self.check_break_position(history_dataframe.loc[start_time])

            # 決策是否交易
            trade_record, df = self.get_trade_record_by_date(start_time)

            # 紀錄交易紀錄
            trade_svc.build_txn_detail_list_df(history_dataframe.loc[start_time], self.invest_amt, self.guarantee_amt,
                                               self.leverage,
                                               trade_record,
                                               self.trade_detail)

        # 製圖
        analysis_df = self.build_analysis_df(history_dataframe)
        chart_dataframe = self.build_chart_dataframe(history_dataframe)
        chart_service.export_trade_point_chart(self.test_name, analysis_df, {
            "start_time": type_util.datetime_to_str(self.start_time, "%Y-%m-%d %H:%M:%S")
            , "end_time": type_util.datetime_to_str(self.end_time, "%Y-%m-%d %H:%M:%S")
            , "initial_capital": self.initial_capital
            , "product": self.product
            , "leverage": self.leverage
            , "other_args": self.other_args})
