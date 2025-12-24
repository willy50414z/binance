from datetime import datetime
from decimal import ROUND_HALF_UP
from zoneinfo import ZoneInfo

from com.willy.binance.config import const
from com.willy.binance.config.config_util import config_util
from com.willy.binance.enums.binance_product import BinanceProduct
from com.willy.binance.service import trade_svc, telegram_svc
from com.willy.binance.service.binance_svc import BinanceSvc
from com.willy.binance.strategy.moving_average_strategy import MovingAverageStrategy
from com.willy.binance.util import type_util
from com.willy.binance.websocket import websocket_listener

maStrategy = MovingAverageStrategy("ma_with_ma25_2504_061", type_util.str_to_datetime("2025-04-01T00:00:00Z"),
                                   type_util.str_to_datetime("2025-11-30T00:00:00Z"), 50000
                                   , BinanceProduct.BTCUSDT, 20, {"level_amt_change": 1, "dca_levels": 5})
config = config_util("linebot")
line_user_id = config.get("userid_willy")


def handle_socket_message(msg):
    if 'k' in msg:
        kline = msg['k']

        is_closed = kline['x']
        if is_closed:
            status = "已收盤" if is_closed else "更新中"

            # K 線開始時間 (Open time, 單位: 毫秒)
            # 將毫秒時間戳轉換為秒，然後格式化為易讀日期時間
            open_time_ms = kline['t']
            open_time_sec = open_time_ms / 1000
            open_time_dt = datetime.fromtimestamp(open_time_sec)

            print("=" * 40)
            print(f"[{status}] 交易對: {kline['s']} ({kline['i']} K 線)")
            print(f"開始時間: {open_time_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"開盤價 (O): {kline['o']}")
            print(f"最高價 (H): {kline['h']}")
            print(f"最低價 (L): {kline['l']}")
            print(f"收盤價 (C): {kline['c']}")
            print(f"交易量 (V): {kline['v']}")
            print("=" * 40)

        # 如果 K 線已收盤，您可以在這裡執行一些邏輯，例如：
        # if is_closed:
        #     print(f"--- 15 分鐘 K 線 {open_time_dt} 已經結束，準備執行策略 ---")

    # 處理其他類型的訊息（如果有的話）
    elif 'e' in msg:
        # 這是事件類型，例如 kline (K 線), aggTrade (聚合交易) 等
        # 這裡我們只處理 kline 類型
        pass
    else:
        # 處理任何其他類型的控制訊息或錯誤
        print(f"收到未處理的訊息: {msg}")


def lambda_handler(event, context):
    now_utc_time = datetime.now().astimezone(ZoneInfo("UTC"))

    # 先撈歷史價格
    binance_svc = BinanceSvc(is_demo=False, is_testnet=False)
    history_kline = binance_svc.get_klines(BinanceProduct.BTCUSDT, maStrategy.tickets_interval,
                                           datetime.now() - maStrategy.get_lookback_timedelta(), datetime.now())

    # 監聽socket，能即時取得最新價格
    websocket_listener.listen_kline_socket(handle_socket_message, BinanceProduct.BTCUSDT, maStrategy.tickets_interval)

    # 條件判斷

    # 發通知

    # now_utc_time = type_util.str_to_date_min("202512061800")
    trade_record, df = maStrategy.get_trade_record_by_date(now_utc_time)
    print(
        f"{type_util.datetime_to_str(datetime.now(), "%Y/%m/%d %H:%M:%S")} start check ma_7_25_break trade record, now_utc_time[{type_util.datetime_to_str(now_utc_time, "%Y/%m/%d %H:%M:%S")}]trade_record[{trade_record}]df[{df[len(df) - 2:]}]")
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
