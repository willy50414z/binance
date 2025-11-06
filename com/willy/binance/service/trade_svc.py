import math
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR
from typing import List

from com.willy.binance.config.config_util import config_util
from com.willy.binance.dto.trade_detail import TradeDetail
from com.willy.binance.dto.trade_record import TradeRecord
from com.willy.binance.enum.handle_fee_type import HandleFeeType
from com.willy.binance.enum.trade_type import TradeType


def calc_profit(current_price, avg_price, total_amt, fee_rate=0.0004):
    """
    計算損益 (USDT)
    :param current_price: 現價
    :param avg_price: 開倉均價
    :param total_amt: 倉位金額 (USDT)
    :param fee_rate: 手續費率 (預設 0.0004 即 0.04%)
    """
    y = (total_amt / avg_price) * (current_price * Decimal(1 - fee_rate) - avg_price)
    return y


def calc_force_close_offset_price(profit: Decimal, avg_price: Decimal, traded_amt: Decimal):
    """
    根據損益反推現價
    :param profit: 損益 (USDT)
    :param avg_price: 開倉均價
    :param total_amt: 倉位金額 (USDT)
    :return: 現價 (current_price)
    """
    current_price = (avg_price * Decimal(1 + profit / traded_amt)) / Decimal(0.9996)
    return current_price


def calc_buyable_units(invest_amt: Decimal, price_per_btc: Decimal, handle_fee_ratio: Decimal = Decimal(
    config_util("binance.trade.handle.fee").get(HandleFeeType.TAKER.name))) -> Decimal:
    """
    計算在手續費以 BTC 計算、投資金額以法幣計，且成交價固定時，
    無條件捨去到小數點第 3 位的可購買 BTC 數量。

    Parameters:
        invest_amt (Decimal): 總投資金額（法幣，單位元）
        price_per_btc (Decimal): BTC 價格，單位元/BTC
        handle_fee_ratio (Decimal): 手續費，以 BTC 為單位

    Returns:
        Decimal: 無條件捨去到小數點第 3 位的 BTC 數量
    """
    # 手續費換算成法幣
    fee_in_currency = handle_fee_ratio * price_per_btc
    usable_money = invest_amt - fee_in_currency
    if usable_money <= Decimal("0"):
        return Decimal("0")
    btc = usable_money / price_per_btc
    # 無條件捨去到小數點第3位
    btc_floor = btc.quantize(Decimal("0.001"), rounding=ROUND_FLOOR)
    return btc_floor


def calc_trade_amt(price: Decimal, units: Decimal, handle_fee: Decimal = Decimal(
    config_util("binance.trade.handle.fee").get(HandleFeeType.TAKER.name))) -> Decimal:
    return price * units * (1 + handle_fee)


def create_trade_record(date: datetime, trade_type: TradeType, price: Decimal, amt: Decimal,
                        handle_fee_type: HandleFeeType = HandleFeeType.TAKER) -> TradeRecord | None:
    handle_fee = Decimal(config_util("binance.trade.handle.fee").get(handle_fee_type.name))
    buyable_units = calc_buyable_units(amt, price, handle_fee)
    if buyable_units > 0:
        return TradeRecord(date, trade_type, price, buyable_units, calc_trade_amt(price, buyable_units, handle_fee))
    else:
        return None


def build_trade_detail_list(current_price: Decimal, invest_amt: Decimal, leverage_ratio: Decimal,
                            trade_record_list: List[TradeRecord],
                            end_datetime: datetime = None, trade_detail_list=None):
    """

    Args:
        trade_detail_list:
        current_price:
        invest_amt: 投資金額(未被槓桿放大)
        leverage_ratio: 槓桿倍數
        trade_record_list: 交易紀錄
        end_datetime:

    Returns:

    """
    if trade_detail_list is None:
        trade_detail_list = []
    trade_record_list.sort(key=lambda tr: tr.date)
    for trade_record in trade_record_list:
        if end_datetime and end_datetime < trade_record.date:
            break

        hold_units = Decimal(0)
        traded_amt = Decimal(0)
        if len(trade_detail_list) > 0:
            last_trade_detail = trade_detail_list[len(trade_detail_list) - 1]
            hold_units = last_trade_detail.units
            traded_amt = last_trade_detail.amt
        if trade_record.type == TradeType.BUY:
            total_trade_amt = traded_amt + trade_record.amt
            total_trade_unit = hold_units + trade_record.unit
            guarantee = total_trade_amt / leverage_ratio
            avg_price = total_trade_amt / total_trade_unit
            profit = calc_profit(current_price, avg_price, total_trade_amt)
            force_close_offset_price = calc_force_close_offset_price(-1 * invest_amt, avg_price, total_trade_amt)
            acct_balance = invest_amt - guarantee
            trade_detail_list.append(
                TradeDetail(trade_record, total_trade_unit, avg_price, total_trade_amt,
                            guarantee,
                            current_price, profit, force_close_offset_price, acct_balance))
        elif trade_record.type == TradeType.SELL:
            total_trade_amt = traded_amt + trade_record.amt
            total_trade_unit = hold_units - trade_record.unit
            guarantee = total_trade_amt / leverage_ratio
            avg_price = total_trade_amt / total_trade_unit * -1
            profit = calc_profit(current_price, avg_price, total_trade_amt) * -1
            force_close_offset_price = calc_force_close_offset_price(invest_amt, avg_price, total_trade_amt)
            acct_balance = invest_amt - guarantee
            trade_detail_list.append(
                TradeDetail(trade_record, total_trade_unit, avg_price, total_trade_amt,
                            guarantee,
                            current_price, profit, force_close_offset_price, acct_balance))

    return trade_detail_list
