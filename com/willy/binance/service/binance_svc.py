import datetime
import functools
import logging
from datetime import timezone
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

import pandas as pd
from binance import Client, ORDER_TYPE_MARKET, ORDER_TYPE_LIMIT, TIME_IN_FORCE_GTC, ORDER_TYPE_STOP_LOSS
from pandas import DataFrame

from com.willy.binance.config import const
from com.willy.binance.config.config_util import config_util
from com.willy.binance.dto.acct_dto import AcctDto, AcctBalance
from com.willy.binance.dto.binance_kline import BinanceKline
from com.willy.binance.dto.commission_order import CommissionOrder
from com.willy.binance.dto.futures_account_info import FuturesAccountInfo
from com.willy.binance.dto.position_info import PositionInfo
from com.willy.binance.dto.time_series_dto import TimeSeriesDto
from com.willy.binance.enums.api_user import ApiUser
from com.willy.binance.enums.binance_product import BinanceProduct
from com.willy.binance.enums.currency import Currency
from com.willy.binance.enums.order_type import OrderType
from com.willy.binance.enums.trade_type import TradeType
from com.willy.binance.enums.transfer_type import TransferType
from com.willy.binance.util import type_util


def parse_datetime_row(row):
    row['start_time'] = type_util.timestamp_to_datetime(row['start_time'] // 1000, tz=timezone.utc)
    row['end_time'] = type_util.timestamp_to_datetime(row['end_time'] // 1000, tz=timezone.utc)
    return row


class BinanceSvc:

    def __init__(self, api_user: ApiUser = ApiUser.HEDGE_BUY, is_demo: bool = True, is_testnet: bool = True):
        self.config = config_util("binance.acct." + api_user.acct_name)
        self.client = None
        self.client = Client(self.config.get("apikey"), self.config.get("privatekey"), demo=is_demo, testnet=is_testnet)

    def get_historical_klines(self, binance_product: BinanceProduct, kline_interval=Client.KLINE_INTERVAL_1DAY,
                              start_date: datetime = type_util.str_to_date("20250101"),
                              end_date: datetime = type_util.str_to_date("20250105")) -> List[BinanceKline]:
        klines = self.client.get_historical_klines(binance_product.name, kline_interval,
                                                   int(start_date.timestamp() * 1000),
                                                   int(end_date.timestamp() * 1000))

        kline_list = []
        for kline in klines:
            kline_list.append(
                BinanceKline(start_time=type_util.timestamp_to_datetime(kline[0] // 1000, tz=timezone.utc),
                             open=Decimal(kline[1]),
                             high=Decimal(kline[2]), low=Decimal(kline[3]), close=Decimal(kline[4]),
                             vol=Decimal(kline[5]),
                             end_time=type_util.timestamp_to_datetime(kline[6] // 1000, tz=timezone.utc),
                             number_of_trade=kline[8]))
        return kline_list

    def acct(self):
        acct_dto = AcctDto()
        for balance in self.client.get_account()["balances"]:
            if float(balance["free"]) > 0 or float(balance["locked"]) > 0:
                acct_dto.balances.append(
                    AcctBalance(balance["asset"], float(balance["free"]), float(balance["locked"])))

        return acct_dto

    def get_historical_klines_df(self, binance_product: BinanceProduct, kline_interval=Client.KLINE_INTERVAL_1DAY,
                                 start_time: datetime = type_util.str_to_date("20250101"),
                                 end_time: datetime = type_util.str_to_date("20250105")) -> DataFrame:
        # 先從檔案讀取，避免頻繁呼叫API
        cached_df = self.get_price_from_cached_file(binance_product, kline_interval)

        # 需要的資料在檔案中，直接撈
        if cached_df is not None and cached_df.index[0] <= start_time and cached_df.index[-1] >= end_time:
            return cached_df.loc[start_time:end_time].copy()
        else:
            query_start_time = start_time
            query_end_time = end_time
            if cached_df is not None:
                if cached_df.index[0] > start_time:
                    query_end_time = cached_df.index[0]
                elif cached_df.index[-1] < end_time:
                    query_start_time = cached_df.index[-1]

            # 需要的資料不在檔案中，call API撈
            klines = self.client.get_historical_klines(binance_product.name, kline_interval,
                                                       int(query_start_time.timestamp() * 1000),
                                                       int(query_end_time.timestamp() * 1000))
            selected_fields = [[row[i] for i in (0, 1, 2, 3, 4, 5, 6, 8)] for row in klines]
            new_data_df = pd.DataFrame(selected_fields,
                                       columns=['start_time', 'open', 'high', 'low', 'close', 'vol', 'end_time',
                                                'number_of_trade'])
            new_data_df = new_data_df.apply(parse_datetime_row, axis=1)
            new_data_df = new_data_df.astype(
                {'open': float, 'high': float, 'low': float, 'close': float, 'vol': float, 'number_of_trade': float})
            new_data_df = new_data_df.set_index('start_time', drop=False).sort_index()

            # merge dataframes
            if cached_df is not None:
                # 合併舊資料與新資料
                updated_df = pd.concat([cached_df, new_data_df])
                # 根據 index (start_time) 去重，保留最新抓到的資料 (以防萬一 API 修正過歷史數據)
                updated_df = updated_df[~updated_df.index.duplicated(keep='last')].sort_index()
            else:
                updated_df = new_data_df

            # export
            data_dir = const.PROJECT_DIR / "data"
            csv_path = data_dir / f"{binance_product.name}_{kline_interval}.csv"
            updated_df.to_csv(csv_path, index=False)

            # clear cache
            self.get_price_from_cached_file.cache_clear()

            return updated_df.loc[start_time:end_time].copy()

    @functools.lru_cache(maxsize=10)
    def get_price_from_cached_file(self, binance_product: BinanceProduct, kline_interval):
        project_dir = str(Path.cwd().parent.parent.parent).replace("\\", "/")

        csv_path = f"{project_dir}/data/{binance_product.name}_{kline_interval}.csv"
        df = None
        if Path(csv_path).exists():
            df = pd.read_csv(csv_path, parse_dates=["start_time", "end_time"])
            df = df.set_index('start_time', drop=False).sort_index()
        return df

    def get_close_ma(self, binance_product: BinanceProduct, kline_interval=Client.KLINE_INTERVAL_1DAY,
                     start_date: datetime = type_util.str_to_datetime("2025-11-10T00:00:00Z"),
                     end_date: datetime = type_util.str_to_datetime("2025-11-10T01:00:00Z"), interval: int = 7):
        klines = self.get_historical_klines(binance_product, kline_interval, start_date, end_date)
        return self.calc_close_ma(klines, interval)

    def calc_close_ma(self, klines: List[BinanceKline], interval: int = 7) -> List[TimeSeriesDto]:
        df = pd.DataFrame({
            'time': [kline.start_time for kline in klines],
            'close': [kline.close for kline in klines]
        })
        df['time'] = pd.to_datetime(df['time'])
        df = df.sort_values('time').reset_index(drop=True)
        df['avg_price'] = df['close'].astype(float).rolling(window=interval, min_periods=interval).mean()

        # 將結果轉換為 List[TimeSeriesDto]
        dtos: List[TimeSeriesDto] = [
            TimeSeriesDto(date=t, value=ap)
            for t, ap in zip(df['time'], df['avg_price'])
        ]
        return dtos

    def universal_transfer(self, type: TransferType, asset: Currency, amount=0.0):
        """

        Args:
            type:
                MAIN_UMFUTURE: 現貨到U本位
                UMFUTURE_MAIN: U本位到現貨
            asset:
            amount:

        Returns:

        """
        try:
            result = self.client.universal_transfer(
                type=type.name,  # UMFUTURE_MAIN 表示從 U 本位合約轉到現貨
                asset=asset.name,  # 要轉移的資產
                amount=amount  # 轉移數量（字串格式）
            )
            return result
        except Exception as e:
            print(f"轉帳失敗: {e}")

    def get_account_info(self) -> FuturesAccountInfo:
        """取得完整帳戶資訊"""
        try:
            account_data = self.client.futures_account()
            return FuturesAccountInfo.from_api_response(account_data)
        except Exception as e:
            raise Exception(f"取得帳戶資訊失敗: {e}")

    def get_futures_positions(self, symbol: Optional[str] = None) -> List[PositionInfo]:
        """
        取得持有倉位
        參數:
            symbol: 指定交易對（可選）
        """
        try:
            if symbol:
                position_data = self.client.futures_position_information(symbol=symbol)
            else:
                position_data = self.client.futures_position_information()

            # 過濾出有持倉的
            positions = [
                PositionInfo.from_api_response(pos)
                for pos in position_data
                if float(pos['positionAmt']) != 0
            ]

            return positions
        except Exception as e:
            raise Exception(f"取得倉位失敗: {e}")

    def get_open_orders(self, symbol: Optional[str] = None) -> List[CommissionOrder]:
        """
        取得當前委託單
        參數:
            symbol: 指定交易對（可選）
        """
        try:
            if symbol:
                orders_data = self.client.futures_get_open_orders(symbol=symbol)
            else:
                orders_data = self.client.futures_get_open_orders()

            orders = [CommissionOrder.from_api_response(order) for order in orders_data]
            return orders
        except Exception as e:
            raise Exception(f"取得委託單失敗: {e}")

    @functools.lru_cache(maxsize=10)
    def get_klines(self, binance_product: BinanceProduct, kline_interval=Client.KLINE_INTERVAL_1DAY,
                   start_time: datetime = type_util.str_to_date("20250101"),
                   end_time: datetime = type_util.str_to_date("20250105")):
        klines = self.client.get_klines(symbol=binance_product.name, interval=kline_interval,
                                        startTime=int(start_time.timestamp() * 1000),
                                        endTime=int(end_time.timestamp() * 1000))
        selected_fields = [[row[i] for i in (0, 1, 2, 3, 4, 5, 6, 8)] for row in klines]
        df = pd.DataFrame(selected_fields,
                          columns=['start_time', 'open', 'high', 'low', 'close', 'vol', 'end_time',
                                   'number_of_trade'])
        df = df.apply(parse_datetime_row, axis=1)
        df = df.astype(
            {'open': float, 'high': float, 'low': float, 'close': float, 'vol': float, 'number_of_trade': float})
        return df

    def create_test_spot_order(self, binance_product: BinanceProduct, trade_type: TradeType, order_type: OrderType,
                               unit: Decimal, price: str = None):
        req_msg = f"product[{binance_product}]trade_type[{trade_type.name}]order_type[{order_type.name}]qty[{unit}]"
        try:
            if order_type.bianace_type == ORDER_TYPE_MARKET:  # 市價單
                result = self.client.create_test_order(
                    symbol=binance_product.name,
                    side=trade_type.bianace_type,
                    type=order_type.bianace_type,
                    quantity=unit
                )
            elif order_type.bianace_type == ORDER_TYPE_LIMIT or order_type.bianace_type == ORDER_TYPE_STOP_LOSS:  # 限價單
                if price is None or not price[len(price) - 3:].startswith("."):
                    raise ValueError(f"ORDER_TYPE_LIMIT need to provide price format '6000.00', price[{price}]")
                result = self.client.create_test_order(
                    symbol=binance_product.name,
                    side=trade_type.bianace_type,
                    type=order_type.bianace_type,
                    timeInForce=TIME_IN_FORCE_GTC,  # GTC: Good Till Cancel (掛單直到取消)
                    quantity=unit,
                    price=price  # 必須是字串格式，並符合價格精度
                )
            else:
                raise ValueError(f"ORDER_TYPE is not in {OrderType.value}")
            logging.info(f"[create_test_spot_order] success, {req_msg}")
            return result
        except Exception as e:
            logging.error(f"[create_test_spot_order] fail, {req_msg}", e)

    def create_test_future_order(self, binance_product: BinanceProduct, trade_type: TradeType, order_type: OrderType,
                                 unit: Decimal, price: str = None):
        req_msg = f"product[{binance_product}]trade_type[{trade_type.name}]order_type[{order_type.name}]qty[{unit}]"
        try:
            if order_type.bianace_type == ORDER_TYPE_MARKET:  # 市價單
                result = self.client.futures_create_test_order(
                    symbol=binance_product.name,
                    side=trade_type.bianace_type,
                    type=order_type.bianace_type,
                    quantity=unit
                )
            elif order_type.bianace_type == ORDER_TYPE_LIMIT or order_type.bianace_type == ORDER_TYPE_STOP_LOSS:  # 限價單
                if price is None or not price[len(price) - 3:].startswith("."):
                    raise ValueError(f"ORDER_TYPE_LIMIT need to provide price format '6000.00', price[{price}]")
                result = self.client.futures_create_test_order(
                    symbol=binance_product.name,
                    side=trade_type.bianace_type,
                    type=order_type.bianace_type,
                    timeInForce=TIME_IN_FORCE_GTC,  # GTC: Good Till Cancel (掛單直到取消)
                    quantity=unit,
                    price=price  # 必須是字串格式，並符合價格精度
                )
            else:
                raise ValueError(f"ORDER_TYPE is not in {OrderType.value}")
            logging.info(f"[create_test_future_order] success, {req_msg}")
            return result
        except Exception as e:
            logging.error(f"[create_test_future_order] fail, {req_msg}", e)

    def create_future_order(self, binance_product: BinanceProduct, trade_type: TradeType, order_type: OrderType,
                            unit: Decimal, price: str = None):
        req_msg = f"product[{binance_product}]trade_type[{trade_type.name}]order_type[{order_type.name}]qty[{unit}]"
        try:
            if order_type.bianace_type == ORDER_TYPE_MARKET:  # 市價單
                result = self.client.futures_create_order(
                    symbol=binance_product.name,
                    side=trade_type.bianace_type,
                    type=order_type.bianace_type,
                    quantity=unit
                )
            elif order_type.bianace_type == ORDER_TYPE_LIMIT or order_type.bianace_type == ORDER_TYPE_STOP_LOSS:  # 限價單
                if price is None or not price[len(price) - 3:].startswith("."):
                    raise ValueError(f"ORDER_TYPE_LIMIT need to provide price format '6000.00', price[{price}]")
                result = self.client.futures_create_order(
                    symbol=binance_product.name,
                    side=trade_type.bianace_type,
                    type=order_type.bianace_type,
                    timeInForce=TIME_IN_FORCE_GTC,  # GTC: Good Till Cancel (掛單直到取消)
                    quantity=unit,
                    price=price  # 必須是字串格式，並符合價格精度
                )
            else:
                raise ValueError(f"ORDER_TYPE is not in {OrderType.value}")
            logging.info(f"[create_future_order] success, {req_msg}")
            return result
        except Exception as e:
            logging.error(f"[create_future_order] fail, {req_msg}", e)

    def change_futures_leverage(self, binance_product: BinanceProduct, leverage: int):
        req_msg = f"product[{binance_product}]leverage[{leverage}]"
        try:
            result = self.client.futures_change_leverage(
                symbol=binance_product.name,
                leverage=leverage
            )
            logging.info(f"[change_futures_leverage] success, {req_msg}")
            return result
        except Exception as e:
            logging.error(f"[change_futures_leverage] fail, {req_msg}", e)


if __name__ == '__main__':
    service = BinanceSvc(ApiUser.WILLY_MOCK, is_demo=False)
    result = service.create_future_order(BinanceProduct.BTCUSDT, TradeType.BUY, order_type=OrderType.LIMIT,
                                         unit=Decimal("0.01"), price="89856.00")
    print(result)

    # print(service.get_klines(BinanceProduct.BTCUSDT, Client.KLINE_INTERVAL_15MINUTE,
    #                          type_util.str_to_date_min("202512040500"), datetime.datetime.now()))
    # # U本位/幣本位 轉帳
    # service.universal_transfer(TransferType.MAIN_UMFUTURE, Currency.USDC, 0.2)
    # account_info = service.get_account_info()
    # print(account_info)
    #
    # 取得所有持倉（使用獨立方法）
    futures_positions = service.get_futures_positions()
    print(futures_positions)
    #
    # # 取得特定交易對的持倉
    # # btc_positions = service.get_positions(symbol='BTCUSDT')
    #
    # 取得所有委託單
    orders = service.get_open_orders()
    opened_order_log = ""
    for order in orders:
        opened_order_log = f"{opened_order_log}\r\nproduct[{order.symbol}]side[{order.side}]unit[{order.orig_qty}]price[{order.price}]"
    print(opened_order_log)
