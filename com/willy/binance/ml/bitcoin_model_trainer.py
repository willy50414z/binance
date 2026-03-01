import os
import sys
import pandas as pd
from datetime import datetime, timedelta, timezone

# Ensure project root is in sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if repo_root not in sys.path:
    sys.path.append(repo_root)

from com.willy.binance.config.config_util import config_util

configured_root = config_util("project.path").get("root_dir")
if configured_root not in sys.path:
    sys.path.append(configured_root)

from com.willy.binance.service.binance_svc import BinanceSvc
from com.willy.binance.enums.binance_product import BinanceProduct
from com.willy.binance.enums.api_user import ApiUser
from com.willy.binance.ml.bitcoin_trading_model import BitcoinTradingModel

def train_and_save():
    print("Initializing Binance Service...")
    # Using HEDGE_BUY as default user, connect to Mainnet for history
    svc = BinanceSvc(api_user=ApiUser.HEDGE_BUY, is_demo=False, is_testnet=False)
    
    # Define Dates
    # Total 6 years: 4 years train + 2 years test
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=365 * 6)
    
    # Split date (cutoff for training)
    split_date = end_date - timedelta(days=365 * 2) 
    
    print(f"Fetching 1h klines from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
    
    # Fetch Data
    # 1h interval to balance granularity and speed
    df = svc.get_historical_klines_df(
        binance_product=BinanceProduct.BTCUSDT,
        kline_interval="1h", 
        start_time=start_date,
        end_time=end_date
    )
    
    print(f"Fetched {len(df)} rows.")
    
    # Initialize Model
    model = BitcoinTradingModel()

    # 1. Calculate Features on FULL dataset first
    # This prevents edge effects for Moving Averages, RSI, etc. at the split boundary.
    print("Calculating features on full dataset...")
    df = model.calculate_features(df, drop_na=True)
    
    # Ensure index is datetime
    if not isinstance(df.index, pd.DatetimeIndex):
         df.index = pd.to_datetime(df['start_time'])

    # 2. Strict Train/Test Split
    print(f"Splitting data at {split_date}...")
    train_df = df[df.index <= split_date].copy()
    test_df = df[df.index > split_date].copy()
    
    print(f"Training Data: {len(train_df)} rows.")
    print(f"Test/Backtest Data: {len(test_df)} rows.")
    
    if len(train_df) < 1000:
        print("Warning: Training data is very small. Check data fetching.")
        return
    
    # 3. Train HMM (ONLY on Training Data) - Prevents Leakage
    print("Training HMM on Training Data...")
    model.train_hmm(train_df)
    
    # 4. Filter Regimes (on Training Data)
    print("Filtering High Volatility Regimes from Training Data...")
    train_filtered = model.filter_regime(train_df, max_vol_rank=1)
    print(f"Training data reduced from {len(train_df)} to {len(train_filtered)} rows after filtering.")
    
    # 5. Train LightGBM (ONLY on Filtered Training Data)
    # Note: train_lgbm splits this further into train/val for early stopping
    print("Training LightGBM on Filtered Training Data...")
    model.train_lgbm(train_filtered)
    
    print("Training Complete.")

    # 6. Save Model
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_dir = os.path.join(script_dir, 'models')
    os.makedirs(model_dir, exist_ok=True)
    
    model_path = os.path.join(model_dir, 'bitcoin_model_v1.pkl')
    model.save_model(model_path)
    
    # 7. Verification / Sanity Check on Test Data
    print("Running sanity check on Test Data...")
    if len(test_df) > 0:
        try:
            # We predict on the Test set to see if code runs.
            # Real performance evaluation should be done via Backtesting (Freqtrade).
            preds = model.predict(test_df)
            
            # Simple stats
            n_long = sum(preds > 0.5) # Assuming binary output is 0 or 1, or probability?
            # predict returns probability or class? 
            # LGBMRegressor returns float. LGBMClassifier predict returns class?
            # In train_lgbm we used lgb.train which returns a Booster. predict returns raw scores/probs.
            # If objective='binary', it returns probabilities.
            
            print(f"Test Set Predictions (first 10): {preds[:10]}")
            print(f"Average Prediction Probability: {preds.mean():.4f}")
            print(f"Min: {preds.min():.4f}, Max: {preds.max():.4f}")
            
        except Exception as e:
            print(f"Prediction on test set failed: {e}")

if __name__ == "__main__":
    train_and_save()
