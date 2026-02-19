
import pandas as pd
import numpy as np
import sys
import os

# Ensure the project root is in sys.path
# Assuming we run from e:\code\binance
project_root = os.getcwd()
if project_root not in sys.path:
    sys.path.append(project_root)

# Also try to compute it relative to the file
file_path = os.path.abspath(__file__)
# e:\code\binance\com\willy\binance\ml\test_bitcoin_model.py
# Go up 5 levels to get e:\code\binance
root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(file_path)))))
if root_path not in sys.path:
    sys.path.append(root_path)

try:
    from com.willy.binance.ml.bitcoin_trading_model import BitcoinTradingModel
except ImportError:
    # If standard import fails, try import without 'com.willy.binance' prefix if we are somehow inside
    # This is a fallback
    sys.path.append(os.path.dirname(file_path))
    from bitcoin_trading_model import BitcoinTradingModel

def generate_mock_data(n_rows=500):
    dates = pd.date_range(start='2024-01-01', periods=n_rows, freq='1h')
    data = {
        'start_time': dates,
        'open': np.random.uniform(50000, 60000, n_rows),
        'high': np.random.uniform(50000, 60000, n_rows),
        'low': np.random.uniform(50000, 60000, n_rows),
        'close': np.random.uniform(50000, 60000, n_rows),
        'vol': np.random.uniform(10, 100, n_rows)
    }
    # Adjust high/low
    df = pd.DataFrame(data)
    df['high'] = df[['open', 'close']].max(axis=1) + np.random.uniform(0, 100, n_rows)
    df['low'] = df[['open', 'close']].min(axis=1) - np.random.uniform(0, 100, n_rows)
    return df

def test_pipeline():
    print("Generating mock data...")
    df = generate_mock_data(500)
    
    model = BitcoinTradingModel()
    
    print("\n--- Test 1: Feature Calculation ---")
    df = model.calculate_features(df)
    print("Features calculated. Columns:", df.columns.tolist())
    assert 'rsi' in df.columns
    assert 'atr' in df.columns
    assert 'target' in df.columns

    print("\n--- Test 2: HMM Training ---")
    model.train_hmm(df, n_components=3)
    assert model.hmm_model is not None
    
    print("\n--- Test 3: Regime Filtering ---")
    df_filtered = model.filter_regime(df, max_vol_rank=1)
    print(f"Original rows: {len(df)}, Filtered rows: {len(df_filtered)}")
    assert len(df_filtered) <= len(df)

    print("\n--- Test 4: Feature Selection ---")
    model.select_features(df_filtered, n_features=5)
    print("Selected features:", model.selected_features)
    assert len(model.selected_features) == 5

    print("\n--- Test 5: LightGBM Training ---")
    model.train_lgbm(df_filtered)
    assert model.lgbm_model is not None
    
    print("\n--- Test 6: Prediction ---")
    preds = model.predict(df.iloc[:10]) # Predict on first 10 rows
    print("Predictions:", preds)
    assert len(preds) == 10

    print("\nAll tests passed successfully!")

if __name__ == "__main__":
    test_pipeline()
