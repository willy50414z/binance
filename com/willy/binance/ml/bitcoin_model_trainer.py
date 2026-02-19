
import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Ensure project root is in sys.path
project_root = os.getcwd()
if project_root not in sys.path:
    sys.path.append(project_root)

# Try also adding com parent
if 'e:\\code\\binance' not in sys.path:
    sys.path.append('e:\\code\\binance')

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
    from datetime import timezone
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
    
    # Split Data
    # Convert index to datetime if it's not already
    if not isinstance(df.index, pd.DatetimeIndex):
         df.index = pd.to_datetime(df['start_time'])

    train_df = df[df.index <= split_date].copy()
    test_df = df[df.index > split_date].copy()
    
    print(f"Training Data (up to {split_date.strftime('%Y-%m-%d')}): {len(train_df)} rows.")
    print(f"Backtest Data (after {split_date.strftime('%Y-%m-%d')}): {len(test_df)} rows.")
    
    if len(train_df) < 1000:
        print("Warning: Training data is very small. Check data fetching.")
    
    # Train Model
    model = BitcoinTradingModel()
    print("Starting full pipeline training...")
    model.full_pipeline_train(train_df)
    
    # Save Model
    # Determine save path
    # e:\code\binance\com\willy\binance\ml\models
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_dir = os.path.join(script_dir, 'models')
    os.makedirs(model_dir, exist_ok=True)
    
    model_path = os.path.join(model_dir, 'bitcoin_model_v1.pkl')
    model.save_model(model_path)
    print(f"Model saved successfully to: {model_path}")
    
    # Optional: Quick validation on test set
    print("validating on test set (first 100 rows)...")
    try:
        if len(test_df) > 0:
            validation_sample = test_df.iloc[:100].copy()
            # Calculate features first because predict expects them
            validation_sample = model.calculate_features(validation_sample)
            # Filter? No, predict should handle it or we skip bad regimes manually
            # But the model pipeline stored 'selected_features' which rely on columns existing
            preds = model.predict(validation_sample)
            print(f"Predictions generated: {preds[:10]}")
    except Exception as e:
        print(f"Validation failed (expected if features need full calculation): {e}")

if __name__ == "__main__":
    train_and_save()
