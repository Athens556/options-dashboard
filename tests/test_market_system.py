import pandas as pd
from datetime import date, timedelta
import data_loader
from market_state import MarketStateBuilder
from tokens import Tokenizer
from db_manager import DBManager
import strategy

def test_pipeline():
    symbol = "NIFTY"
    print(f"Testing pipeline for {symbol}...")
    
    # 1. Fetch Data
    end_date = date.today()
    start_date = end_date - timedelta(days=365)
    
    print("Fetching Market Data...")
    data, error = data_loader.process_market_data(symbol, start_date, end_date)
    
    if error:
        print(f"Data Fetch Error: {error}")
        return

    spot_series = data['spot']
    iv_series = data['iv']
    rv_series = data['rv']
    vix_series = data['vix']
    
    print(f"Got {len(spot_series)} spot records.")
    
    # 2. Build States
    builder = MarketStateBuilder()
    db = DBManager()
    
    # Iterate over last 10 days to save time
    test_dates = spot_series.index[-10:]
    
    print("\n--- Generating States & Tokens ---")
    for d in test_dates:
        # Handle both date and datetime
        d_date = d.date() if hasattr(d, "date") else d
        
        state = builder.build_daily_state(
            symbol, d_date, spot_series, iv_series, rv_series
        )
        
        if state:
            # Save to DB
            db.save_market_state(state)
            
            # Tokenize
            tokens = Tokenizer.get_tokens(state)
            
            print(f"\nDate: {d_date}")
            print(f"  Price: {state.spot_price:.2f}")
            print(f"  Regime: {state.regime_label} | Vol: {state.volatility_regime}")
            print(f"  Tokens: {tokens}")
            
            # Check Strategies
            active_strategies = []
            for strat in strategy.get_all_strategies():
                if strat.should_enter(tokens):
                    active_strategies.append(strat.name)
            
            if active_strategies:
                print(f"  >> SIGNALS: {active_strategies}")
            else:
                print(f"  >> No Signals")

if __name__ == "__main__":
    test_pipeline()
