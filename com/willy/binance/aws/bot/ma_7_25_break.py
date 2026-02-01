import concurrent.futures
import copy
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from com.willy.binance.dto.cool_down_period_setting_dto import CoolDownPeriodSettingDto
from com.willy.binance.dto.trade_detail import TradeDetail
from com.willy.binance.enums.binance_product import BinanceProduct
from com.willy.binance.strategy.ma_7_25_break_strategy import Ma725BreakStrategy
from com.willy.binance.strategy.trade_strategy import TradingStrategy
from com.willy.binance.util import type_util


def get_strategy():
    return Ma725BreakStrategy("bot_ma_7_25_break",
                              type_util.str_to_datetime("2025-01-01T00:00:00Z"),
                              type_util.str_to_datetime("2025-12-21T00:00:00Z"), Decimal("6000")
                              , BinanceProduct.BTCUSDT, Decimal("20"), {}, CoolDownPeriodSettingDto(2, 96),
                              is_aws_profile=True)


def check_price_worker(price, df_template, check_time):
    # 此處需完整複製 strategy 與 dataframe 以確保多執行緒執行時不互相干擾
    # strategy_template: 只讀取不修改，作為複製來源
    local_strategy = get_strategy()
    local_df = df_template.copy()

    # 修改最後一根K棒的收盤價
    close_price = float(price)
    last_idx = local_df.index[-1]
    local_df.at[last_idx, 'close'] = close_price

    if close_price > local_df.at[last_idx, 'high']:
        local_df.at[last_idx, 'high'] = close_price
    if close_price < local_df.at[last_idx, 'low']:
        local_df.at[last_idx, 'low'] = close_price

    # 重算指標
    local_strategy.append_tech_ides(local_df)

    is_triggered = False
    try:
        local_strategy.handle_trade(check_time, local_df, False)
        if len(local_strategy.trade_detail.txn_detail_list) > 0 and \
                local_strategy.trade_detail.txn_detail_list[-1].trade_record is not None and \
                local_strategy.trade_detail.txn_detail_list[-1].trade_record.date == check_time:
            is_triggered = True
    except Exception:
        pass

    return price, is_triggered


def get_tradable_price_interval_list(maStrategy, dt):
    maStrategy.start_time = dt
    maStrategy.end_time = dt

    # 撈出最新的價格
    full_back_test_df = maStrategy.get_backtest_dataframe()

    # 預計算未來的可交易價格帶
    # Init trade_detail if needed
    if not maStrategy.has_init_trade_detail:
        if maStrategy.is_aws_profile:
            maStrategy.trade_detail = maStrategy.s3_svc.get_trade_detail(maStrategy.test_name)
        else:
            maStrategy.trade_detail = TradeDetail([])
        maStrategy.has_init_trade_detail = True

    # 保存原始狀態模板
    original_trade_detail = copy.deepcopy(maStrategy.trade_detail)
    # 將原始的 trade_detail 放回 strategy 中，作為模板傳入 worker
    maStrategy.trade_detail = original_trade_detail

    original_df = full_back_test_df.copy()

    current_close = float(full_back_test_df.iloc[-1]['close'])

    start_price = int(current_close) - 1000
    end_price = int(current_close) + 1000
    step = 1  # 最小區間

    print(f"開始預計算可交易價格帶 (多執行緒逼近法)，範圍: {start_price} ~ {end_price}，最小精度: {step}")

    # 記錄每個價格的檢查結果: {price: is_triggered}
    results = {}

    # 使用 ThreadPoolExecutor
    # 建議 worker 數依照 CPU 核心數調整，或是因應 Python GIL 與 clone 開銷適度設定
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:

        def batch_check(prices):
            futures = []
            for p in prices:
                # 尚未檢查過的才送出任務
                if p not in results:
                    futures.append(
                        executor.submit(check_price_worker, p, original_df, test_datetime)
                    )

            # 等待當批次完成
            for future in concurrent.futures.as_completed(futures):
                p, triggered = future.result()
                results[p] = triggered

        # 1. 初始檢查點: 中間(當前價), 下界, 上界
        # 這樣我們可以形成最初的兩個區間: [start, current] 和 [current, end]
        initial_points = {start_price, int(current_close), end_price}
        batch_check(initial_points)

        # 待檢查的區間隊列: (low, high)
        # 初始區間
        interval_queue = [
            (start_price, int(current_close)),
            (int(current_close), end_price)
        ]

        # 迭代深度/區間細分
        while interval_queue:
            next_interval_queue = []
            points_to_check = set()

            # 遍歷當前層的所有區間，找出需要細分的點
            current_intervals = []  # 暫存 (low, high, mid)

            for low, high in interval_queue:
                # 如果區間已經很小，就不再細分
                if high - low <= step:
                    continue

                # 檢查邊界狀態
                is_low_trig = results.get(low, False)
                is_high_trig = results.get(high, False)

                # 優化邏輯: 如果區間兩端狀態一致 (都是 True 或都是 False)，則假設中間不用測
                # 這裡依照需求: "如果有測到上限限都是需要做交易的就不需要再往裡面測了"
                if is_low_trig == is_high_trig:
                    continue

                # 否則需要細分，加入中點
                mid = (low + high) // 2
                points_to_check.add(mid)
                current_intervals.append((low, high, mid))

            if not points_to_check:
                break

            # 批次執行新點的檢查
            batch_check(points_to_check)

            # 產生下一層的區間
            for low, high, mid in current_intervals:
                next_interval_queue.append((low, mid))
                next_interval_queue.append((mid, high))

            interval_queue = next_interval_queue

    # 整理結果並輸出 Range
    # 從 results 中找出連續的觸發區間
    # 這裡簡單做法是將所有 checked points 排序，若發現某段區間兩端都是 True，則視為該區間有效
    # 但更好的顯示方式是重建連續區段。
    # 由於我們跳過了一些點，我們只能基於已知點來推斷。

    sorted_prices = sorted(results.keys())
    trigger_ranges = []

    if sorted_prices:
        current_range_start = None

        for i in range(len(sorted_prices) - 1):
            p1 = sorted_prices[i]
            p2 = sorted_prices[i + 1]

            s1 = results[p1]
            s2 = results[p2]

            # 如果 p1 是觸發點
            if s1:
                if current_range_start is None:
                    current_range_start = p1

            # 檢查區段 [p1, p2] 是否連續
            # 如果 s1 和 s2 都是 True，且距離不算太遠(或是我們主動跳過了中間)，視為連續
            # 如果 s1 True, s2 False -> 斷開。 Range end at p1?
            # 由於我們是二分逼近，分界點會在 p1, p2 之間。
            # 我們這裡保守輸出: 僅顯示已確認的點覆蓋範圍。

            if s1 and not s2:
                # p1 True -> p2 False, 結束這段
                trigger_ranges.append((current_range_start, p1))
                current_range_start = None
            elif not s1 and s2:
                # p1 False -> p2 True, 新段開始 (會在下一次迴圈處理 s2 時被視為 s1)
                pass
            elif not s1 and not s2:
                # 都 False
                pass
            else:
                # 都 True -> 連續
                pass

        # 處理最後一個點
        last_p = sorted_prices[-1]
        if results[last_p]:
            if current_range_start is None:
                trigger_ranges.append((last_p, last_p))
            else:
                trigger_ranges.append((current_range_start, last_p))
        else:
            if current_range_start is not None:
                trigger_ranges.append((current_range_start, sorted_prices[-2]))

    if trigger_ranges:
        logging.info("預測可交易價格區間 (Trigger Ranges):")
        for s, e in trigger_ranges:
            logging.info(f"  {s} ~ {e}")
        return trigger_ranges
    else:
        return None


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
    maStrategy = get_strategy()
    maStrategy.start_time = trade_time
    maStrategy.end_time = trade_time
    maStrategy.run_backtest()
    return maStrategy


def lambda_handler(event, context):
    # get kline interval start time
    trade_time = previous_quarter_hour(datetime.now().astimezone(ZoneInfo("UTC")))  # FIXME

    # get tradable price interval
    maStrategy = get_strategy()
    tradable_price_interval_list = get_tradable_price_interval_list(maStrategy, trade_time)

    if tradable_price_interval_list and len(tradable_price_interval_list) > 0:
        tradable_price_interval = tradable_price_interval_list[0]
        current_price = maStrategy.binance_svc.get_futures_symbol_ticker(maStrategy.product)['price']

        if tradable_price_interval[0] <= current_price <= tradable_price_interval[1]:
            # create trade record and trade
            pass
        else:
            # 還沒進入交易價格，等進入了再出手
            pass

    # TODO
    """
    上面已經算出需要執行交易的收盤價格區間，接下來
    1. 參考com/willy/binance/websocket/websocket_listener.py:90方法監聽binance websocket，如果收到價格區間結束的消息，
    """

    # if maStrategy.trade_detail.txn_detail_list is not None and len(maStrategy.trade_detail.txn_detail_list) > 0 and \
    #         maStrategy.trade_detail.txn_detail_list[-1].date == trade_time:
    #     # 需要做交易
    #     trade_record = maStrategy.trade_detail.txn_detail_list[-1].trade_record
    #     telegram_svc.push_message(
    #         message=f"pg_start_time[{type_util.datetime_to_str_ms(now_utc_time, "%Y/%m/%d %H:%M:%S")}]\r\n"
    #                 f"trade_time[{type_util.datetime_to_str_ms(trade_time, "%Y/%m/%d %H:%M:%S")}]\r\n"
    #                 f"msg_time[{type_util.datetime_to_str_ms(datetime.now(), "%Y/%m/%d %H:%M:%S")}]\r\n")
    #     telegram_svc.push_message(
    #         message=f"===TradeRecord===\r\n"
    #                 f"date[{trade_record.date}]\r\nproduct[{maStrategy.product.name}]\r\nside[{trade_record.type.name}]"
    #                 f"\r\nunit[{trade_record.unit}]\r\nprice[{trade_record.price}]"
    #                 f"\r\nreason_type[{trade_record.reason.trade_reason_type.name}]\r\nreason[{trade_record.reason.desc}]")
    #     telegram_svc.push_message(
    #         message=f"\r\n===Trade_Detail==="
    #                 f"\r\n[{json.dumps(maStrategy.trade_detail, cls=EnhanceJSONEncoder, ensure_ascii=False)}]")
    return {
        'statusCode': 200,
        'body': 'Hello from Lambda Container!'
    }


if __name__ == '__main__':
    # run_strategy(type_util.str_to_datetime(f"2026-01-27T06:15:00Z"))
    test_datetime = type_util.str_to_datetime(f"2026-01-27T06:15:00Z")
    maStrategy = get_strategy()

    maStrategy.start_time = test_datetime
    maStrategy.end_time = test_datetime

    full_back_test_df = maStrategy.get_backtest_dataframe()
    maStrategy.append_tech_ides(full_back_test_df)
    maStrategy.handle_trade(test_datetime, full_back_test_df, False)
    print(maStrategy.trade_detail)
