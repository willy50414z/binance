import datetime
from decimal import ROUND_HALF_UP
from zoneinfo import ZoneInfo

from com.willy.binance.config import const
from com.willy.binance.config.config_util import config_util
from com.willy.binance.enums.binance_product import BinanceProduct
from com.willy.binance.service import trade_svc, telegram_svc
from com.willy.binance.strategy.moving_average_strategy import MovingAverageStrategy
from com.willy.binance.util import type_util

maStrategy = MovingAverageStrategy("ma_with_ma25_2504_061", type_util.str_to_datetime("2025-04-01T00:00:00Z"),
                                   type_util.str_to_datetime("2025-11-30T00:00:00Z"), 50000
                                   , BinanceProduct.BTCUSDT, 20, {"level_amt_change": 1, "dca_levels": 5})
config = config_util("linebot")
line_user_id = config.get("userid_willy")


def lambda_handler(event, context):
    now_utc_time = datetime.datetime.now().astimezone(ZoneInfo("UTC"))
    # now_utc_time = type_util.str_to_date_min("202512061800")
    trade_record, df = maStrategy.get_trade_record_by_date(now_utc_time)
    print(
        f"{type_util.datetime_to_str(datetime.datetime.now(), "%Y/%m/%d %H:%M:%S")} start check ma_7_25_break trade record, now_utc_time[{type_util.datetime_to_str(now_utc_time, "%Y/%m/%d %H:%M:%S")}]trade_record[{trade_record}]df[{df[len(df) - 2:]}]")
    # service.create_future_order(maStrategy.product, trade_record.type,
    #                             OrderType.MARKET if trade_record.handle_fee_type == HandleFeeType.TAKER else OrderType.LIMIT,
    #                             trade_record.unit,
    #                             str(trade_record.price.quantize(const.DECIMAL_PLACE_2, rounding=ROUND_HALF_UP)))
    if trade_record:
        trade_svc.build_txn_detail_list_df(df.iloc[-1], maStrategy.invest_amt, maStrategy.guarantee_amt,
                                           maStrategy.leverage,
                                           trade_record,
                                           maStrategy.trade_detail)
        trade_detail_log = ""
        for txn_detail in maStrategy.trade_detail.txn_detail_list:
            trade_detail_log = f"{trade_detail_log}\r\nunits[{txn_detail.units}]handle_amt[{txn_detail.handle_amt}]profit[{txn_detail.profit}]total_profit[{txn_detail.total_profit}]acct_balance[{txn_detail.acct_balance}]\r\n"
        telegram_svc.push_message(
            message=f"UTC time[{type_util.datetime_to_str(now_utc_time, "%Y/%m/%d %H:%M:%S")}]\r\n===TradeRecord===\r\ndate[{trade_record.date}]product[{maStrategy.product.name}]\r\nside[{trade_record.type.name}]\r\nunit[{trade_record.unit}]\r\nprice[{trade_record.price.quantize(const.DECIMAL_PLACE_2, rounding=ROUND_HALF_UP)}]reason[{trade_record.reason}]\r\n===TradeDetail===\r\n{trade_detail_log}")
        telegram_svc.push_message(
            message=f"{df[len(df) - 2:]}")

    return {
        'statusCode': 200,
        'body': 'Hello from Lambda Container!'
    }


if __name__ == '__main__':
    lambda_handler(1, 1)
