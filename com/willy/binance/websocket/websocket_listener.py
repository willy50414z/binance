import datetime
import logging
import time

from binance import ThreadedWebsocketManager, Client

from com.willy.binance.enums.binance_product import BinanceProduct

# --- 配置參數 ---
# ⚠️ 注意：使用 ThreadedWebsocketManager 不一定需要 API Key 和 Secret，
# 但如果您計劃做交易操作，就需要它們。
# 這裡僅監聽數據，可留空，但如果函式庫強制要求，則需要填入無權限的虛設值。
API_KEY = ''
API_SECRET = ''

SYMBOL = 'BTCUSDT'  # 交易對
INTERVAL = '15m'  # K 線間隔


def listen_kline_socket(msg_handler, product: BinanceProduct, kline_interval=Client.KLINE_INTERVAL_15MINUTE):
    twm = ThreadedWebsocketManager(api_key=API_KEY, api_secret=API_SECRET)
    twm.start()  # 啟動執行緒管理器

    logging.info(f"開始監聽 {SYMBOL} 的 {INTERVAL} K 線...")

    # 啟動 K 線串流訂閱
    # ks_klines 是 K-line Stream 的縮寫，它會呼叫 handle_socket_message 函式來處理數據
    kline_stream = twm.start_kline_socket(
        callback=msg_handler,
        symbol=product.name,
        interval=kline_interval
    )

    # 主執行緒進入一個無限循環，保持程式運行，直到手動中斷 (Ctrl+C)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n--- 接收到中斷訊號，停止 WebSocket 連線 ---")
        twm.stop()  # 停止所有 WebSocket 連線和執行緒
        print("程式已安全退出。")


def handle_socket_message(msg):
    """
    處理從 WebSocket 接收到的 K 線訊息

    :param msg: 包含 K 線資料的字典
    """
    if 'k' in msg:
        kline = msg['k']

        # K 線開始時間 (Open time, 單位: 毫秒)
        # 將毫秒時間戳轉換為秒，然後格式化為易讀日期時間
        open_time_ms = kline['t']
        open_time_sec = open_time_ms / 1000
        open_time_dt = datetime.datetime.fromtimestamp(open_time_sec)

        # K 線狀態: True=已收盤/結束, False=當前K線仍在更新 (Trade in progress)
        is_closed = kline['x']
        if is_closed:
            status = "已收盤" if is_closed else "更新中"

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


if __name__ == '__main__':
    # 建立 ThreadedWebsocketManager 實例
    # 它會在一個單獨的執行緒中處理 WebSocket 連線
    twm = ThreadedWebsocketManager(api_key=API_KEY, api_secret=API_SECRET)
    twm.start()  # 啟動執行緒管理器

    print(f"開始監聽 {SYMBOL} 的 {INTERVAL} K 線...")

    # 啟動 K 線串流訂閱
    # ks_klines 是 K-line Stream 的縮寫，它會呼叫 handle_socket_message 函式來處理數據
    kline_stream = twm.start_kline_socket(
        callback=handle_socket_message,
        symbol=SYMBOL,
        interval=INTERVAL
    )

    # 主執行緒進入一個無限循環，保持程式運行，直到手動中斷 (Ctrl+C)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n--- 接收到中斷訊號，停止 WebSocket 連線 ---")
        twm.stop()  # 停止所有 WebSocket 連線和執行緒
        print("程式已安全退出。")
