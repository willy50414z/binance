
import sys
import os
import pandas as pd
import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter

# Add project root to path to find the ml module
# Strategy is in e:\code\binance\com\willy\binance\freqtrade\BitcoinMLStrategy.py
# Root is e:\code\binance
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file)))))
if project_root not in sys.path:
    sys.path.append(project_root)

# Try imports
try:
    from com.willy.binance.ml.bitcoin_trading_model import BitcoinTradingModel
except ImportError:
    # If standard import fails, try to just import from ml dir if path allows
    # But usually sys.path append works
    print("Could not import BitcoinTradingModel. ML features will be disabled.")
    BitcoinTradingModel = None

class BitcoinMLStrategy(IStrategy):
    """
    BitcoinMLStrategy
    Uses a pre-trained LightGBM model to predict price movements.
    """
    INTERFACE_VERSION = 3
    
    # Strategy parameters
    minimal_roi = { "0": 100 } # Let signal decide exit
    stoploss = -0.05
    trailing_stop = True
    
    # Timeframe must match what was used for training (1h in our trainer)
    timeframe = '1h' 
    
    can_short = True
    
    process_only_new_candles = True
    
    use_exit_signal = True
    exit_profit_only = False
    
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.model = None
        if BitcoinTradingModel is not None:
            self.model = BitcoinTradingModel()
            # Construct path to model file
            # e:\code\binance\com\willy\binance\ml\models\bitcoin_model_v1.pkl
            model_path = os.path.join(project_root, 'com', 'willy', 'binance', 'ml', 'models', 'bitcoin_model_v1.pkl')
            
            if os.path.exists(model_path):
                print(f"Loading model from {model_path}")
                try:
                    self.model.load_model(model_path)
                    print("Model loaded successfully.")
                except Exception as e:
                    print(f"Failed to load model: {e}")
                    self.model = None
            else:
                print(f"Model file not found at {model_path}. Please run bitcoin_model_trainer.py first.")
                self.model = None

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if self.model:
            # Calculate features using the model's logic
            # drop_na=False to preserve Freqtrade's dataframe length
            try:
                dataframe = self.model.calculate_features(dataframe, drop_na=False)
            except Exception as e:
                print(f"Feature calculation failed: {e}")
                
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'enter_long'] = 0
        dataframe.loc[:, 'enter_short'] = 0
        
        if self.model:
            try:
                # Predict
                preds = self.model.predict(dataframe)
                dataframe['ml_prob'] = preds
                
                # Signal Logic
                # Prob > 0.6 -> High chance of Uptrend -> Long
                dataframe.loc[
                    (dataframe['ml_prob'] > 0.6) & 
                    (dataframe['volume'] > 0), 
                    'enter_long'
                ] = 1
                
                # Prob < 0.4 -> Low chance of Uptrend (likely Downtrend) -> Short
                if self.can_short:
                    dataframe.loc[
                        (dataframe['ml_prob'] < 0.4) & 
                        (dataframe['volume'] > 0), 
                        'enter_short'
                    ] = 1
                    
            except Exception as e:
                print(f"Prediction failed: {e}")
                
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'exit_long'] = 0
        dataframe.loc[:, 'exit_short'] = 0
        
        if 'ml_prob' in dataframe.columns:
            # Exit Long if prob drops below neutral (e.g. 0.5)
            dataframe.loc[
                (dataframe['ml_prob'] < 0.5) & 
                (dataframe['volume'] > 0),
                'exit_long'
            ] = 1
            
            # Exit Short if prob rises above neutral
            dataframe.loc[
                (dataframe['ml_prob'] > 0.5) & 
                (dataframe['volume'] > 0),
                'exit_short'
            ] = 1
            
        return dataframe
