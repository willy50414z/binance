import unittest
from datetime import datetime
from decimal import Decimal

from com.willy.binance.dto.binance_kline import BinanceKline
from com.willy.binance.dto.trade_detail import TradeDetail
from com.willy.binance.dto.trade_record import TradeRecord
from com.willy.binance.dto.txn_detail import TxnDetail
from com.willy.binance.enums.handle_fee_type import HandleFeeType
from com.willy.binance.enums.trade_reason import TradeReason, TradeReasonType
from com.willy.binance.enums.trade_type import TradeType
from com.willy.binance.service.trade_svc import build_txn_detail_list, create_trade_record


class TestBuildTxnDetailList(unittest.TestCase):

    def setUp(self):
        """初始化基礎參數"""
        self.invest_amt = Decimal("10000")
        self.leverage = Decimal("10")
        self.trade_detail = TradeDetail(txn_detail_list=[])

        # 建立符合用戶定義格式的基礎 Kline (價格 50000)
        self.base_kline = BinanceKline(
            start_time=datetime(2025, 1, 1, 0, 0),
            open=Decimal("50000"),
            high=Decimal("51000"),
            low=Decimal("49000"),
            close=Decimal("50500"),
            vol=Decimal("1"),
            end_time=datetime(2025, 1, 1, 0, 14, 59),
            number_of_trade=100
        )

    def test_tc01_full_test_build_txn_detail_list(self):
        """[TC-01] 測試情境：初始無交易紀錄 (應回傳淨值等於初始投入)"""
        trade_record = create_trade_record(datetime(2025, 1, 1, 0, 0), TradeType.BUY, Decimal("50000"), None,
                                           Decimal("0.2"),
                                           HandleFeeType.TAKER, TradeReason(TradeReasonType.ACTIVE, ""))
        build_txn_detail_list(self.base_kline, self.invest_amt, self.leverage, trade_record, self.trade_detail)

        trade_record = create_trade_record(datetime(2025, 1, 1, 0, 0), TradeType.BUY, Decimal("52000"), None,
                                           Decimal("0.1"),
                                           HandleFeeType.MAKER, TradeReason(TradeReasonType.ACTIVE, ""))
        build_txn_detail_list(self.base_kline, self.invest_amt, self.leverage, trade_record, self.trade_detail)

        trade_record = create_trade_record(datetime(2025, 1, 1, 0, 0), TradeType.SELL, Decimal("53000"), None,
                                           Decimal("0.1"),
                                           HandleFeeType.TAKER, TradeReason(TradeReasonType.ACTIVE, ""))
        build_txn_detail_list(self.base_kline, self.invest_amt, self.leverage, trade_record, self.trade_detail)

        trade_record = create_trade_record(datetime(2025, 1, 1, 0, 0), TradeType.SELL, Decimal("52000"), None,
                                           Decimal("0.4"),
                                           HandleFeeType.TAKER, TradeReason(TradeReasonType.ACTIVE, ""))
        build_txn_detail_list(self.base_kline, self.invest_amt, self.leverage, trade_record, self.trade_detail)

        trade_record = create_trade_record(datetime(2025, 1, 1, 0, 0), TradeType.SELL, Decimal("51000"), None,
                                           Decimal("0.1"),
                                           HandleFeeType.MAKER, TradeReason(TradeReasonType.ACTIVE, ""))
        build_txn_detail_list(self.base_kline, self.invest_amt, self.leverage, trade_record, self.trade_detail)

        trade_record = create_trade_record(datetime(2025, 1, 1, 0, 0), TradeType.BUY, Decimal("49000"), None,
                                           Decimal("0.1"),
                                           HandleFeeType.TAKER, TradeReason(TradeReasonType.ACTIVE, ""))
        build_txn_detail_list(self.base_kline, self.invest_amt, self.leverage, trade_record, self.trade_detail)

        trade_record = create_trade_record(datetime(2025, 1, 1, 0, 0), TradeType.BUY, Decimal("50000"), None,
                                           Decimal("0.4"),
                                           HandleFeeType.TAKER, TradeReason(TradeReasonType.ACTIVE, ""))
        build_txn_detail_list(self.base_kline, self.invest_amt, self.leverage, trade_record, self.trade_detail)

        trade_record = create_trade_record(datetime(2025, 1, 1, 0, 0), TradeType.SELL, Decimal("51000"), None,
                                           Decimal("0.2"),
                                           HandleFeeType.TAKER, TradeReason(TradeReasonType.ACTIVE, ""))
        build_txn_detail_list(self.base_kline, self.invest_amt, self.leverage, trade_record, self.trade_detail)

        result_list = [TxnDetail(date=datetime(2025, 1, 1, 0, 0), units=Decimal('0.2'), handle_amt=Decimal('10000.0'),
                                 handling_fee=Decimal('4.00'), guarantee_fee=Decimal('1000.00'),
                                 current_price=Decimal('50000'), profit=Decimal('0'), profit_ratio=Decimal('0'),
                                 total_profit=Decimal('0'), force_close_offset_price=Decimal('21'),
                                 break_even_point_price=Decimal('50041'), max_loss=Decimal('-207.92'),
                                 acct_balance=Decimal('8996.00'),
                                 trade_record=TradeRecord(date=datetime(2025, 1, 1, 0, 0),
                                                          type=TradeType.BUY, price=Decimal('50000'),
                                                          unit=Decimal('0.2'),
                                                          handle_fee_type=HandleFeeType.TAKER,
                                                          reason=TradeReason(trade_reason_type=TradeReasonType.ACTIVE,
                                                                             desc='')))
            , TxnDetail(date=datetime(2025, 1, 1, 0, 0), units=Decimal('0.3'), handle_amt=Decimal('15200.0'),
                        handling_fee=Decimal('5.04'), guarantee_fee=Decimal('1520.00'), current_price=Decimal('52000'),
                        profit=Decimal('0'), profit_ratio=Decimal('0'), total_profit=Decimal('0'),
                        force_close_offset_price=Decimal('17358'), break_even_point_price=Decimal('50704'),
                        max_loss=Decimal('-510.92'), acct_balance=Decimal('8474.96'),
                        trade_record=TradeRecord(date=datetime(2025, 1, 1, 0, 0), type=TradeType.BUY,
                                                 price=Decimal('52000'), unit=Decimal('0.1'),
                                                 handle_fee_type=HandleFeeType.MAKER,
                                                 reason=TradeReason(trade_reason_type=TradeReasonType.ACTIVE, desc='')))
            , TxnDetail(date=datetime(2025, 1, 1, 0, 0), units=Decimal('0.2'),
                        handle_amt=Decimal('10133.33333333333333333333333'), handling_fee=Decimal('3.36'),
                        guarantee_fee=Decimal('1013.34'), current_price=Decimal('53000'), profit=Decimal('229.53'),
                        profit_ratio=Decimal('0.004528695748251895424148834857'), total_profit=Decimal('229.53'),
                        force_close_offset_price=Decimal('684'), break_even_point_price=Decimal('50704'),
                        max_loss=Decimal('-340.62'), acct_balance=Decimal('9212.83'),
                        trade_record=TradeRecord(date=datetime(2025, 1, 1, 0, 0), type=TradeType.SELL,
                                                 price=Decimal('53000'), unit=Decimal('0.1'),
                                                 handle_fee_type=HandleFeeType.TAKER,
                                                 reason=TradeReason(trade_reason_type=TradeReasonType.ACTIVE, desc='')))
            , TxnDetail(date=datetime(2025, 1, 1, 0, 0), units=Decimal('-0.2'), handle_amt=Decimal('10400.0'),
                        handling_fee=Decimal('4.16'), guarantee_fee=Decimal('1040.00'), current_price=Decimal('52000'),
                        profit=Decimal('259.14'), profit_ratio=Decimal('0.002556454964932680216559772287'),
                        total_profit=Decimal('488.67'), force_close_offset_price=Decimal('101938'),
                        break_even_point_price=Decimal('51958'), max_loss=Decimal('0'), acct_balance=Decimal('9444.51'),
                        trade_record=TradeRecord(date=datetime(2025, 1, 1, 0, 0), type=TradeType.SELL,
                                                 price=Decimal('52000'), unit=Decimal('0.4'),
                                                 handle_fee_type=HandleFeeType.TAKER,
                                                 reason=TradeReason(trade_reason_type=TradeReasonType.ACTIVE, desc='')))
            , TxnDetail(date=datetime(2025, 1, 1, 0, 0), units=Decimal('-0.3'), handle_amt=Decimal('15500.0'),
                        handling_fee=Decimal('5.18'), guarantee_fee=Decimal('1550.00'), current_price=Decimal('51000'),
                        profit=Decimal('0'), profit_ratio=Decimal('0'), total_profit=Decimal('488.67'),
                        force_close_offset_price=Decimal('84948'), break_even_point_price=Decimal('51628'),
                        max_loss=Decimal('0'), acct_balance=Decimal('8933.49'),
                        trade_record=TradeRecord(date=datetime(2025, 1, 1, 0, 0), type=TradeType.SELL,
                                                 price=Decimal('51000'), unit=Decimal('0.1'),
                                                 handle_fee_type=HandleFeeType.MAKER,
                                                 reason=TradeReason(trade_reason_type=TradeReasonType.ACTIVE, desc='')))
            , TxnDetail(date=datetime(2025, 1, 1, 0, 0), units=Decimal('-0.2'),
                        handle_amt=Decimal('10333.33333333333333333333333'),
                        handling_fee=Decimal('3.453333333333333333333333334'), guarantee_fee=Decimal('1033.34'),
                        current_price=Decimal('49000'), profit=Decimal('256.07'),
                        profit_ratio=Decimal('0.004964489049443909500390975885'), total_profit=Decimal('744.74'),
                        force_close_offset_price=Decimal('101608'), break_even_point_price=Decimal('51628'),
                        max_loss=Decimal('0'), acct_balance=Decimal('9707.95'),
                        trade_record=TradeRecord(date=datetime(2025, 1, 1, 0, 0), type=TradeType.BUY,
                                                 price=Decimal('49000'), unit=Decimal('0.1'),
                                                 handle_fee_type=HandleFeeType.TAKER,
                                                 reason=TradeReason(trade_reason_type=TradeReasonType.ACTIVE, desc='')))
            , TxnDetail(date=datetime(2025, 1, 1, 0, 0), units=Decimal('0.2'), handle_amt=Decimal('10000.0'),
                        handling_fee=Decimal('4.00'), guarantee_fee=Decimal('1000.00'), current_price=Decimal('50000'),
                        profit=Decimal('325.88'), profit_ratio=Decimal('0.003154731710339326303887363648'),
                        total_profit=Decimal('1070.62'), force_close_offset_price=Decimal('21'),
                        break_even_point_price=Decimal('50041'), max_loss=Decimal('-207.92'),
                        acct_balance=Decimal('10066.62'),
                        trade_record=TradeRecord(date=datetime(2025, 1, 1, 0, 0), type=TradeType.BUY,
                                                 price=Decimal('50000'), unit=Decimal('0.4'),
                                                 handle_fee_type=HandleFeeType.TAKER,
                                                 reason=TradeReason(trade_reason_type=TradeReasonType.ACTIVE, desc='')))
            , TxnDetail(date=datetime(2025, 1, 1, 0, 0), units=Decimal('0.0'), handle_amt=Decimal('0.0'),
                        handling_fee=Decimal('0.00'), guarantee_fee=Decimal('0.00'), current_price=Decimal('51000'),
                        profit=Decimal('191.92'), profit_ratio=Decimal('0.00191843262694922031187524990'),
                        total_profit=Decimal('1262.54'), force_close_offset_price=None, break_even_point_price=None,
                        max_loss=Decimal('0'), acct_balance=Decimal('11262.54'),
                        trade_record=TradeRecord(date=datetime(2025, 1, 1, 0, 0), type=TradeType.SELL,
                                                 price=Decimal('51000'), unit=Decimal('0.2'),
                                                 handle_fee_type=HandleFeeType.TAKER,
                                                 reason=TradeReason(trade_reason_type=TradeReasonType.ACTIVE, desc='')))
                       ]

        self.assertEqual(result_list, self.trade_detail.txn_detail_list, "build_txn_detail_list test pass")


if __name__ == '__main__':
    unittest.main()
