import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_FLOOR
from enum import Enum
from typing import List

import pandas as pd

from com.willy.binance.aws.service import s3_svc
from com.willy.binance.config import const
from com.willy.binance.config.const import DECIMAL_PLACE_2
from com.willy.binance.dto.cool_down_period_setting_dto import CoolDownPeriodSettingDto
from com.willy.binance.dto.trade_detail import TradeDetail
from com.willy.binance.dto.trade_record import TradeRecord
from com.willy.binance.enums.binance_product import BinanceProduct
from com.willy.binance.enums.tech_idx_type import TechIdxType
from com.willy.binance.enums.trade_reason import TradeReason, TradeReasonType
from com.willy.binance.service import trade_svc, chart_service, tech_idx_svc
from com.willy.binance.service.binance_svc import BinanceSvc
from com.willy.binance.util import type_util


class IndexSwitch(Enum):
    pass


class TradingStrategy(ABC):
    def __init__(self, test_name, start_time: datetime,
                 end_time: datetime,
                 initial_capital: Decimal,
                 product: BinanceProduct,
                 leverage: Decimal, other_args=None, cool_down_period: CoolDownPeriodSettingDto = None,
                 is_aws_profile: bool = False):
        if other_args is None:
            other_args = {}
        self.last_td = None
        self.test_name = test_name
        self.start_time = start_time
        self.end_time = end_time
        self.initial_capital = initial_capital
        self.product = product
        self.leverage = leverage
        self.other_args = other_args
        # self.guarantee_amt = initial_capital - self.invest_amt
        self.binance_svc = BinanceSvc(is_demo=False, is_testnet=False)
        self.trade_detail = TradeDetail([])
        self.date_idx_map = {}
        self.cool_down_period = cool_down_period
        self.is_aws_profile = is_aws_profile
        # if is_aws_profile:
        #     self.s3_svc = s3_svc.get_backtest_svc(self.test_name)
        self.s3_svc = s3_svc.get_backtest_svc(self.test_name)

    cross_test_config = None

    def get_invest_amt(self):
        # return Decimal("30000")
        if self.last_td is not None:
            return (self.last_td.acct_balance * self.max_invest_ratio).quantize(DECIMAL_PLACE_2,
                                                                                ROUND_FLOOR) * self.leverage
        else:
            return (self.initial_capital * self.max_invest_ratio).quantize(DECIMAL_PLACE_2,
                                                                           ROUND_FLOOR) * self.leverage

    def get_trade_index_switch_status(self, switch: IndexSwitch):
        if self.cross_test_config is None:
            return False
        if switch in self.cross_test_config:
            return self.cross_test_config[switch]
        else:
            return False

    def get_lookback_timedelta(self) -> timedelta:
        required_buffer_ticks = max(self.get_required_buffer_ticks(self.tech_idx_list), self.lookback_ticks)
        return self.get_timedelta_by_tick_count(required_buffer_ticks)

    def get_timedelta_by_tick_count(self, tick_count: int):
        if self.tickets_interval.endswith("m"):
            return timedelta(
                minutes=float(self.tickets_interval[:len(self.tickets_interval) - 1]) * tick_count)
        elif self.tickets_interval.endswith("h"):
            return timedelta(
                hours=float(self.tickets_interval[:len(self.tickets_interval) - 1]) * tick_count)
        elif self.tickets_interval.endswith("d"):
            return timedelta(
                days=float(self.tickets_interval[:len(self.tickets_interval) - 1]) * tick_count)
        elif self.tickets_interval.endswith("w"):
            return timedelta(
                weeks=float(self.tickets_interval[:len(self.tickets_interval) - 1]) * tick_count)
        else:
            raise ValueError(f"unexpect time unit[{self.tickets_interval}]")

    @property
    @abstractmethod
    def lookback_ticks(self) -> int:
        return 0

    @property
    @abstractmethod
    def tickets_interval(self) -> str:
        pass

    @property
    @abstractmethod
    def strategy_idx_switches(self) -> IndexSwitch:
        pass

    @property
    @abstractmethod
    def tech_idx_list(self) -> List[TechIdxType]:
        pass

    @property
    def max_invest_ratio(self) -> Decimal:
        return Decimal("0.25")

    @abstractmethod
    def get_trade_record_by_date(self, dt: datetime) -> TradeRecord:
        """

        """
        pass

    @abstractmethod
    def is_meet_tech_idx_with_switch(self, row):
        """
        確認是否符合各項技術指標
        """
        pass

    # @abstractmethod
    # def build_chart_dataframe(self, history_dataframe):
    #     pass

    def build_analysis_df(self, history_df):
        # 1. 將 txn_detail_list 轉成 DataFrame
        txn_data = []
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
        analysis_df = history_df.join(txn_df, how='left', rsuffix='_txn')

        # 強制將交易相關欄位轉為 float，避免 ffill 噴警告
        numeric_cols = ['profit', 'total_profit', 'acct_balance', 'units', 'trade_price']
        for col in numeric_cols:
            if col in analysis_df.columns:
                analysis_df[col] = pd.to_numeric(analysis_df[col], errors='coerce')

        return analysis_df

    def check_break_position(self, row):
        # 確認有沒有爆倉
        if self.last_td and ((self.last_td.units > 0 and row.low < self.last_td.force_close_offset_price) or (
                self.last_td.units < 0 and row.high > self.last_td.force_close_offset_price)):
            trade_svc.build_txn_detail_list_df(row,
                                               self.initial_capital,
                                               self.leverage,
                                               trade_svc.create_close_trade_record(row.start_time,
                                                                                   self.last_td.force_close_offset_price,
                                                                                   self.last_td,
                                                                                   reason=TradeReason(
                                                                                       TradeReasonType.PASSIVE,
                                                                                       "爆倉")),
                                               self.trade_detail, self.cool_down_period)
            return True
        return False

    def get_required_buffer_ticks(self, tech_idx_type_list: list[TechIdxType]):
        """
        根據選用的指標列表，計算需要往前多抓幾分鐘的資料
        """
        max_warm_up_ticks = 0
        for tech_idx_type in tech_idx_type_list:
            needed = tech_idx_type.base_window * tech_idx_type.warm_up_multiplier
            if needed > max_warm_up_ticks:
                max_warm_up_ticks = int(needed)
        return max_warm_up_ticks

    def append_tech_ides(self, df):
        for tech_idx in self.tech_idx_list:
            tech_idx_method = getattr(tech_idx_svc, tech_idx.method_name)
            tech_idx_method(df, tech_idx.base_window)

    def build_trade_detail_analysis_df(self):
        """
        將 txn_detail_list 轉換為以 '每一筆完整交易' 為單位的 DataFrame
        """
        trades = []
        current_trade = None

        for txn in self.trade_detail.txn_detail_list:
            # 當 units 從 0 變為有值，代表開倉
            if txn.trade_record and txn.units != 0 and (current_trade is None or current_trade['closed']):
                current_trade = {
                    'entry_date': txn.date,
                    'entry_price': txn.trade_record.price,
                    'type': txn.trade_record.type,
                    'units': txn.units,
                    'entry_reason': txn.trade_record.reason.desc if txn.trade_record.reason else "",
                    'closed': False,
                    'max_favorable_price': txn.trade_record.price,  # 最高獲利價
                    'max_adverse_price': txn.trade_record.price,  # 最大回撤價
                }

            # 追蹤持倉期間的價格波動 (MFE/MAE 分析)
            if current_trade and not current_trade['closed']:
                if txn.units > 0:  # 多單
                    current_trade['max_favorable_price'] = max(current_trade['max_favorable_price'],
                                                               txn.trade_record.price)
                    current_trade['max_adverse_price'] = min(current_trade['max_adverse_price'], txn.trade_record.price)
                else:  # 空單
                    current_trade['max_favorable_price'] = min(current_trade['max_favorable_price'],
                                                               txn.trade_record.price)
                    current_trade['max_adverse_price'] = max(current_trade['max_adverse_price'], txn.trade_record.price)

            # 當 units 變回 0，或者發生反手（units 正負號改變），代表前一筆交易結束
            if current_trade and not current_trade['closed']:
                if txn.units == 0 or (txn.trade_record and txn.units * current_trade['units'] < 0):
                    current_trade['exit_date'] = txn.date
                    current_trade['exit_price'] = txn.trade_record.price
                    current_trade['profit'] = txn.profit
                    current_trade[
                        'exit_reason'] = txn.trade_record.reason.desc if txn.trade_record and txn.trade_record.reason else "持有"
                    current_trade['duration'] = (txn.date - current_trade['entry_date']).total_seconds() / 3600  # 持倉小時
                    current_trade['closed'] = True
                    trades.append(current_trade.copy())

        df = pd.DataFrame(trades)
        # 增加關鍵分析欄位
        if not df.empty:
            df['is_win'] = df['profit'] > 0
            df['pnl_ratio'] = df['profit'] / (df['entry_price'] * abs(df['units']))  # 報酬率
        return df

    def is_in_cool_down_period(self, start_time: datetime) -> bool:
        if not self.cool_down_period:
            return False

        # 還在冷靜期
        if self.cool_down_period.next_trade_time is not None and start_time < self.cool_down_period.next_trade_time:
            logging.debug(f"in_cool_down_period,next_trade_time[{self.cool_down_period.next_trade_time}]")
            return True

        if len(self.trade_detail.txn_detail_list) > self.cool_down_period.loss_count:
            # 確認有沒有連續虧損
            traded_txn_list = [td for td in self.trade_detail.txn_detail_list if
                               td.trade_record is not None and td.trade_record.unit != 0
                               and (self.cool_down_period.last_loss_time is None
                                    or (self.cool_down_period.last_loss_time is not None
                                        and td.date > self.cool_down_period.last_loss_time))]
            last_n_txn_detail_list = traded_txn_list[-self.cool_down_period.loss_count:]
            if len(last_n_txn_detail_list) > 0 and len([td for td in last_n_txn_detail_list if td.profit > 0]) == 0:
                # 連續虧損
                self.cool_down_period.next_trade_time = start_time + self.get_timedelta_by_tick_count(
                    self.cool_down_period.cool_down_period)
                self.cool_down_period.last_loss_time = self.last_td.date
                return True
            else:
                return False

    def run_backtest(self):
        logging.info(
            f"start run backtest,test_name[{self.test_name}]start_time[{self.start_time}]end_time[{self.end_time}]"
            f"initial_capital[{self.initial_capital}]product[{self.product.name}]leverage[{self.leverage}]"
            f"is_aws_profile[{self.is_aws_profile}]cool_down_period[{self.cool_down_period}]")

        # 先計算技術指標需要提前撈的資料
        look_back_timedelta = self.get_lookback_timedelta()

        # 獲取回測時間
        if self.is_aws_profile:
            full_back_test_df = \
                self.binance_svc.get_klines(self.product, self.tickets_interval,
                                            self.start_time - look_back_timedelta,
                                            self.end_time)
            self.trade_detail = self.s3_svc.get_trade_detail(self.test_name)
        else:
            full_back_test_df = \
                self.binance_svc.get_historical_klines_df(self.product, self.tickets_interval,
                                                          self.start_time - look_back_timedelta,
                                                          self.end_time)

        # 計算技術指標
        self.append_tech_ides(full_back_test_df)

        backtest_df = full_back_test_df.loc[self.start_time: self.end_time].copy()

        backtest_start_time_list = backtest_df.index
        logging.debug(f"backtest_start_time_list[{backtest_start_time_list}]")
        row_idx = 0
        # 逐日回測
        for start_time in backtest_start_time_list:
            # 準備共用參數
            self.date_idx_map[start_time] = row_idx
            row_idx += 1
            self.last_td = self.trade_detail.txn_detail_list[len(self.trade_detail.txn_detail_list) - 1] if len(
                self.trade_detail.txn_detail_list) > 0 else None
            # if row_idx % 1000 == 0:
            #     print(f"finish {row_idx} / {backtest_start_time_list.shape[0]}")
            logging.debug(f"last_td[{self.last_td}]")
            # 帳戶餘額已歸零須停止回測
            if len(self.trade_detail.txn_detail_list) > 0:
                last_balance = self.trade_detail.txn_detail_list[-1].acct_balance
                if last_balance <= 0:
                    logging.info(f"[testResult][{start_time}] 帳戶餘額已歸零 ({last_balance})，終止回測。")
                    break

            if self.is_in_cool_down_period(start_time):
                logging.info(f"[testResult]in_cool_down_period cool down~~")
                continue

            current_idx = full_back_test_df.index.get_loc(start_time)
            get_trade_record_df = full_back_test_df.iloc[:current_idx]
            prev_row = get_trade_record_df.iloc[-1]
            current_row = backtest_df.loc[start_time]
            if self.last_td:
                self.cool_down_period = self.last_td.cool_down_period

            # 確認有沒有爆倉
            if self.check_break_position(prev_row):
                logging.info("[testResult]爆倉了")

            # 決策是否交易
            logging.debug(f"last 2 get_trade_record_df rows data[{get_trade_record_df[len(get_trade_record_df) - 2:]}]")
            trade_record = self.get_trade_record_by_date(get_trade_record_df)

            if trade_record:
                logging.info(
                    f"[testResult]{trade_record.date} {trade_record.type} {trade_record.unit} in {trade_record.price} because {trade_record.reason}")
            else:
                logging.debug(f"[testResult]not meet trade strategy")
            # 紀錄交易紀錄
            trade_svc.build_txn_detail_list_df(current_row, self.initial_capital,
                                               self.leverage,
                                               trade_record,
                                               self.trade_detail, self.cool_down_period)

            if self.is_aws_profile and trade_record is not None:
                self.s3_svc.write_trade_detail(self.test_name, self.trade_detail)

        if not self.is_aws_profile:
            # 製圖
            analysis_df = self.build_analysis_df(backtest_df)
            # chart_dataframe = self.build_chart_dataframe(history_dataframe)
            chart_service.export_trade_point_chart(self.test_name, analysis_df, {
                "start_time": type_util.datetime_to_str(self.start_time, "%Y-%m-%d %H:%M:%S")
                , "end_time": type_util.datetime_to_str(self.end_time, "%Y-%m-%d %H:%M:%S")
                , "initial_capital": float(self.initial_capital)
                , "product": self.product
                , "leverage": self.leverage
                , "other_args": self.other_args})

            # 交易明細
            strategy_optimization_report_dir = f"{const.PROJECT_DIR}/report"
            os.makedirs(strategy_optimization_report_dir, exist_ok=True)
            self.build_trade_detail_analysis_df().to_csv(
                f"{strategy_optimization_report_dir}/{self.test_name}_trade_detail.csv", index=False)

            return analysis_df
