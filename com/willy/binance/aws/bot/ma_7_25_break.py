import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from com.willy.binance.dto.cool_down_period_setting_dto import CoolDownPeriodSettingDto
from com.willy.binance.dto.trade_detail import TradeDetail
from com.willy.binance.encoder.json_encoder import EnhanceJSONEncoder
from com.willy.binance.enums.binance_product import BinanceProduct
from com.willy.binance.service import telegram_svc
from com.willy.binance.strategy.ma_7_25_break_strategy import Ma725BreakStrategy
from com.willy.binance.strategy.trade_strategy import TradingStrategy
from com.willy.binance.util import type_util

maStrategy = Ma725BreakStrategy("bot_ma_7_25_break",
                                type_util.str_to_datetime("2025-01-01T00:00:00Z"),
                                type_util.str_to_datetime("2025-12-21T00:00:00Z"), Decimal("6000")
                                , BinanceProduct.BTCUSDT, Decimal("20"), {}, CoolDownPeriodSettingDto(2, 96),
                                is_aws_profile=True)


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


# def expect_place_order_price_range(history_kline_df: DataFrame):
#     last_index = history_kline.index[-1]
#     history_kline.at[last_index, 'close'] = 999


def next_quarter_hour(dt: datetime) -> datetime:
    # 將分鐘取模 15，得到距離下個點的偏移分鐘
    minutes_to_add = (15 - dt.minute % 15) % 15
    if minutes_to_add == 0:
        minutes_to_add = 15  # 已在點上時，跳到下一個點
    result = dt + timedelta(minutes=minutes_to_add)
    # 將秒與微秒歸零
    return result.replace(second=0, microsecond=0).astimezone(timezone.utc)


def previous_quarter_hour(dt: datetime) -> datetime:
    # 先把分鐘向下取整到最近的 15 的倍數
    minute_down = (dt.minute // 15) * 15
    # 先把秒、微秒清零，並把時間回到該格點
    dt_down = dt.replace(minute=minute_down, second=0, microsecond=0)

    # 判斷是否剛好就在格點上（且沒有任何偏移）
    is_exact_grid = (dt.minute % 15 == 0) and (dt.second == 0) and (dt.microsecond == 0)

    if is_exact_grid:
        # 如果原本就在格點上，回到上一個格點
        dt_down -= timedelta(minutes=15)

    return dt_down.astimezone(timezone.utc)


def dt_second_or_ms_zero(d: datetime) -> bool:
    return d.second == 0 and d.microsecond == 0


def run_strategy(trade_time: datetime) -> TradingStrategy:
    maStrategy.start_time = trade_time
    maStrategy.end_time = trade_time
    maStrategy.trade_detail = TradeDetail([])
    maStrategy.run_backtest()
    return maStrategy


def lambda_handler(event, context):
    now_utc_time = datetime.now()

    # # 先撈歷史價格
    # history_kline_df = binance_svc.get_klines(BinanceProduct.BTCUSDT, maStrategy.tickets_interval,
    #                                           datetime.now() - maStrategy.get_lookback_timedelta(), datetime.now())

    # 預計算出可下單區間

    # 條件判斷
    # last_row = history_kline_df.iloc[-1]
    trade_time = previous_quarter_hour(datetime.now().astimezone(ZoneInfo("UTC")))  # FIXME

    maStrategy = run_strategy(trade_time)

    if maStrategy.trade_detail.txn_detail_list is not None and len(maStrategy.trade_detail.txn_detail_list) > 0 and \
            maStrategy.trade_detail.txn_detail_list[-1].date == trade_time:
        # 需要做交易
        trade_record = maStrategy.trade_detail.txn_detail_list[-1].trade_record
        telegram_svc.push_message(
            message=f"pg_start_time[{type_util.datetime_to_str_ms(now_utc_time, "%Y/%m/%d %H:%M:%S")}]\r\n"
                    f"trade_time[{type_util.datetime_to_str_ms(trade_time, "%Y/%m/%d %H:%M:%S")}]\r\n"
                    f"msg_time[{type_util.datetime_to_str_ms(datetime.now(), "%Y/%m/%d %H:%M:%S")}]\r\n")
        telegram_svc.push_message(
            message=f"===TradeRecord===\r\n"
                    f"date[{trade_record.date}]\r\nproduct[{maStrategy.product.name}]\r\nside[{trade_record.type.name}]"
                    f"\r\nunit[{trade_record.unit}]\r\nprice[{trade_record.price}]"
                    f"\r\nreason_type[{trade_record.reason.trade_reason_type.name}]\r\nreason[{trade_record.reason.desc}]")
        telegram_svc.push_message(
            message=f"\r\n===Trade_Detail==="
                    f"\r\n[{json.dumps(maStrategy.trade_detail, cls=EnhanceJSONEncoder, ensure_ascii=False)}]")
    return {
        'statusCode': 200,
        'body': 'Hello from Lambda Container!'
    }


if __name__ == '__main__':
    # run_strategy(type_util.str_to_datetime(f"2026-01-27T06:15:00Z"))
    test_datetime = type_util.str_to_datetime(f"2026-01-27T06:15:00Z")
    maStrategy.start_time = test_datetime
    maStrategy.end_time = test_datetime

    full_back_test_df = maStrategy.get_backtest_dataframe()
    maStrategy.append_tech_ides(full_back_test_df)
    maStrategy.handle_trade(test_datetime, full_back_test_df, False)
    print(maStrategy.trade_detail)
