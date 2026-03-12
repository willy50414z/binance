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

import os
import sys
import argparse
import json
import shutil
from pathlib import Path
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


def train(output_path: str = None):
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
    import pandas as pd
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
    if output_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_dir = os.path.join(script_dir, 'models')
        os.makedirs(model_dir, exist_ok=True)
        output_path = os.path.join(model_dir, f'bitcoin_model_{datetime.now().strftime("%Y%m%d%H%M%S")}.pkl')
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    model.save_model(output_path)
    
    # 7. Verification / Sanity Check on Test Data
    print("Running sanity check on Test Data...")
    if len(test_df) > 0:
        try:
            preds = model.predict(test_df)
            print(f"Test Set Predictions (first 10): {preds[:10]}")
            print(f"Average Prediction Probability: {preds.mean():.4f}")
            print(f"Min: {preds.min():.4f}, Max: {preds.max():.4f}")
        except Exception as e:
            print(f"Prediction on test set failed: {e}")

    return output_path


def stage(source_path: str = None, target_dir: str = None):
    if target_dir is None:
        target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'production')
    
    os.makedirs(target_dir, exist_ok=True)

    if source_path is None:
        model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
        if not os.path.exists(model_dir):
            print(f"No models directory found at {model_dir}")
            return
        
        # Find latest .pkl file
        models = sorted([f for f in os.listdir(model_dir) if f.endswith('.pkl')])
        if not models:
            print(f"No .pkl models found in {model_dir}")
            return
        source_path = os.path.join(model_dir, models[-1])

    print(f"📦 Staging model from {source_path} to {target_dir}...")
    model_name = os.path.basename(source_path)
    target_path = os.path.join(target_dir, 'bitcoin_model_production.pkl')
    
    shutil.copy2(source_path, target_path)
    print(f"  - Copied to {target_path}")

    # Create staged_info.json
    info = {
        "staged_at": datetime.now(timezone.utc).isoformat(),
        "source_file": source_path,
        "target_file": target_path
    }
    with open(os.path.join(target_dir, 'staged_info.json'), 'w', encoding='utf-8') as f:
        json.dump(info, f, indent=4)
    print(f"✅ Staged model info saved to {target_dir}/staged_info.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bitcoin Trading Model Trainer")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Train command
    train_parser = subparsers.add_parser("train", help="Train a new model")
    train_parser.add_argument("--output", type=str, help="Output path for the model .pkl")

    # Stage command
    stage_parser = subparsers.add_parser("stage", help="Stage a model to production")
    stage_parser.add_argument("--source", type=str, help="Source model .pkl file")
    stage_parser.add_argument("--target", type=str, help="Target production directory")

    args = parser.parse_args()

    if args.command == "train":
        train(output_path=args.output)
    elif args.command == "stage":
        stage(source_path=args.source, target_dir=args.target)
    else:
        # Default behavior for backward compatibility
        train()
