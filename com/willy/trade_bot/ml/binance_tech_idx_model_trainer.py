from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from com.willy.trade_bot.data_extractor.binance_extractor import BinanceExtractor
from com.willy.trade_bot.dto.crypto_extractor_dto import CryptoExtractorDto
from com.willy.trade_bot.enums.exchange import Exchange
from com.willy.trade_bot.enums.market_type import MarketType
from com.willy.trade_bot.enums.product import Product
from com.willy.trade_bot.enums.timeframe import Timeframe
from com.willy.trade_bot.service.tech_idx_svc import TECHNICAL_INDICATOR_COLUMNS, append_technical_indicators


class BinanceTechIdxModelTrainer:
    def __init__(self, market_type: MarketType = MarketType.FUTURE):
        self.market_type = market_type
        self.extractor = BinanceExtractor()

    def fetch_ohlcv(self) -> dict[str, pd.DataFrame]:
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=730)

        target_timeframes = [
            Timeframe.MINUTE_15,
            Timeframe.HOUR_1,
            Timeframe.HOUR_4,
            Timeframe.DAY_1,
        ]

        data_by_timeframe: dict[str, pd.DataFrame] = {}
        for timeframe in target_timeframes:
            extractor_dto = CryptoExtractorDto(
                exchange=Exchange.BINANCE,
                product=Product.BTCUSDT,
                market_type=self.market_type,
                timeframe=timeframe,
                start_dt=start_dt,
                end_dt=end_dt,
            )
            df = self.extractor.extract(extractor_dto)

            # Keep OHLCV-focused columns for subsequent technical-indicator modeling.
            if not df.empty:
                df = df[["start_time", "open", "high", "low", "close", "vol"]].copy()

            data_by_timeframe[timeframe.value] = df

        return data_by_timeframe

    def make_stationary(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        stationary_df = df.copy()
        stationary_df["log_return"] = np.log(stationary_df["close"] / stationary_df["close"].shift(1))
        return stationary_df

    def lag_features(self, df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        lagged_df = df.copy()
        existing_feature_columns = [col for col in feature_columns if col in lagged_df.columns]
        if not existing_feature_columns:
            return lagged_df

        lagged_df[existing_feature_columns] = lagged_df[existing_feature_columns].shift(1)
        return lagged_df


def train():
    # Fetch OHLCV data.
    trainer = BinanceTechIdxModelTrainer()
    ohlcv_data = trainer.fetch_ohlcv()

    for timeframe, df in ohlcv_data.items():
        # Ensure stationary transform runs before technical indicators.
        df = trainer.make_stationary(df)
        df = append_technical_indicators(df)
        if df is None or df.empty:
            ohlcv_data[timeframe] = df
            print(f"{timeframe}: rows=0")
            continue

        # Shift features by one bar to avoid look-ahead leakage.
        df = trainer.lag_features(df, feature_columns=["log_return", *TECHNICAL_INDICATOR_COLUMNS])
        df = df.dropna(subset=["log_return", *TECHNICAL_INDICATOR_COLUMNS]).reset_index(drop=True)
        ohlcv_data[timeframe] = df

        print(f"{timeframe}: rows={len(df)} column[{df.columns}]")


if __name__ == "__main__":
    train()
