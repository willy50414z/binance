from datetime import timezone

import pandas as pd
from binance import Client

from com.willy.binance.config import const
from com.willy.trade_bot.dto.backtest_config import BackTestConfig
from com.willy.trade_bot.enums.market_type import MarketType
from com.willy.trade_bot.enums.product import Product
from com.willy.trade_bot.utils import type_utils


def parse_datetime_row(row):
    row['start_time'] = type_utils.timestamp_to_datetime(row['start_time'] // 1000, tz=timezone.utc)
    row['end_time'] = type_utils.timestamp_to_datetime(row['end_time'] // 1000, tz=timezone.utc)
    return row


class BinanceExtractor:

    def __init__(self, back_test_config: BackTestConfig):
        self.client = Client("", "")
        self.back_test_config = back_test_config

    def extract(self) -> pd.DataFrame:
        """
        主要抓取流程：
        1. 檢查並讀取現有的 .feature 檔案
        2. 計算需要抓取的缺漏時間範圍
        3. 透過 Binance API 抓取缺漏資料
        4. 合併新舊資料並儲顯
        5. 回傳請求時間範圍內的 DataFrame
        """
        output_path = self._get_feature_file_path()
        existing_df = self._load_existing_feature(output_path)

        start_dt = self.back_test_config.start_dt
        end_dt = self.back_test_config.end_dt

        # 檢查是否需要抓取新資料 (若現有資料已包含請求範圍則跳過)
        fetch_ranges = self._calculate_fetch_ranges(existing_df, start_dt, end_dt)

        df = existing_df
        if fetch_ranges:
            new_data_df = self._fetch_and_process_data(fetch_ranges)

            if new_data_df is not None and not new_data_df.empty:
                df = self._merge_and_save_data(existing_df, new_data_df, output_path)
            elif existing_df is None:
                # 若無現有資料且抓取代失敗或無資料
                df = pd.DataFrame()

        if df is not None and not df.empty:
            return df.loc[start_dt:end_dt].copy()

        return pd.DataFrame()

    def _get_feature_file_path(self):
        """建構 .feature 檔案的路徑"""
        trade_bot_data_dir = const.PROJECT_DIR / "com/willy/trade_bot/data"
        output_dir = trade_bot_data_dir / self.back_test_config.exchange.name / self.back_test_config.market_type.name
        output_dir.mkdir(parents=True, exist_ok=True)

        file_name = f"{self.back_test_config.product.name}_{self.back_test_config.timeframe.value}.feature"
        return output_dir / file_name

    def _load_existing_feature(self, file_path) -> pd.DataFrame:
        """讀取現有的 .feature 檔案"""
        if not file_path.exists():
            return None

        try:
            df = pd.read_feather(file_path)
            if 'start_time' in df.columns:
                pass
            df = df.set_index('start_time', drop=False).sort_index()

            # 若 config 的時間是 timezone-aware，確保讀出來的 df index 也是 (補上 UTC)
            start_dt = self.back_test_config.start_dt
            if start_dt.tzinfo is not None and len(df) > 0:
                if df.index[0].tzinfo is None:
                    df.index = df.index.tz_localize('UTC')
            return df
        except Exception as e:
            print(f"[BinanceExtractor] 讀取現有檔案失敗: {e}")
            return None

    def _calculate_fetch_ranges(self, existing_df: pd.DataFrame, start_dt, end_dt):
        """計算需要透過 API 補抓的時間範圍"""
        if existing_df is not None and not existing_df.empty:
            existing_start = existing_df.index.min()
            existing_end = existing_df.index.max()

            # 若現有資料已完全覆蓋請求範圍，則不需抓取
            if existing_start <= start_dt and existing_end >= end_dt:
                return []

            fetch_ranges = []
            # 補抓頭部缺漏
            if start_dt < existing_start:
                fetch_ranges.append((start_dt, existing_start))

            # 補抓尾部缺漏
            if end_dt > existing_end:
                fetch_ranges.append((existing_end, end_dt))

            return fetch_ranges

        else:
            # 無現有資料，抓取全部範圍
            return [(start_dt, end_dt)]

    def _fetch_and_process_data(self, fetch_ranges) -> pd.DataFrame:
        """根據時間範圍抓取 raw data 並轉換為 DataFrame"""
        timeframe = self.back_test_config.timeframe.value
        product = self.back_test_config.product
        new_data_frames = []

        for qs, qe in fetch_ranges:
            raw_data = []
            if self.back_test_config.market_type == MarketType.FUTURE:
                raw_data = self._get_futures_klines(product, timeframe, qs, qe)
            elif self.back_test_config.market_type == MarketType.SPOT:
                raw_data = self._get_historical_klines_df(product, timeframe, qs, qe)
            else:
                raise ValueError(f"不支援的市場類型: {self.back_test_config.market_type}")

            if raw_data:
                chunk_df = self._convert_raw_to_df(raw_data)
                new_data_frames.append(chunk_df)

        if new_data_frames:
            return pd.concat(new_data_frames)
        return None

    def _convert_raw_to_df(self, raw_data) -> pd.DataFrame:
        """將 API 回傳的 raw data 轉換整理為 DataFrame"""
        # 選取需要的欄位: Open time, Open, High, Low, Close, Volume, Close time, Number of trades
        selected_fields = [[row[i] for i in (0, 1, 2, 3, 4, 5, 6, 8)] for row in raw_data]
        df = pd.DataFrame(selected_fields,
                          columns=['start_time', 'open', 'high', 'low', 'close', 'vol', 'end_time',
                                   'number_of_trade'])
        df = df.apply(parse_datetime_row, axis=1)
        df = df.astype(
            {'open': float, 'high': float, 'low': float, 'close': float, 'vol': float,
             'number_of_trade': float})
        df = df.set_index('start_time', drop=False)
        return df

    def _merge_and_save_data(self, existing_df: pd.DataFrame, new_df: pd.DataFrame, output_path) -> pd.DataFrame:
        """合併新舊資料，去重並儲存"""
        # 處理時區一致性 (以 UTC 為主)
        if existing_df is not None and not existing_df.empty:
            if existing_df.index[0].tzinfo != new_df.index[0].tzinfo:
                if existing_df.index[0].tzinfo is None:
                    existing_df.index = existing_df.index.tz_localize('UTC')
                if new_df.index[0].tzinfo is None:
                    new_df.index = new_df.index.tz_localize('UTC')

            merged_df = pd.concat([existing_df, new_df])
        else:
            merged_df = new_df

        # 去重並排序
        merged_df = merged_df[~merged_df.index.duplicated(keep='last')].sort_index()

        # 儲存
        try:
            merged_df.reset_index(drop=True).to_feather(output_path)
        except (ImportError, AttributeError):
            merged_df.to_pickle(output_path)

        return merged_df

    def _get_futures_klines(self, product: Product, interval, start_time, end_time):
        return self.client.futures_historical_klines(
            symbol=product.name,
            interval=interval,
            start_str=int(start_time.timestamp() * 1000),
            end_str=int(end_time.timestamp() * 1000)
        )

    def _get_historical_klines_df(self, product: Product, interval, start_time, end_time):
        return self.client.get_historical_klines(
            symbol=product.name,
            interval=interval,
            start_str=int(start_time.timestamp() * 1000),
            end_str=int(end_time.timestamp() * 1000)
        )


def extract(back_test_config: BackTestConfig):
    return BinanceExtractor(back_test_config).extract()
