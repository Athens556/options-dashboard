from backtest import BacktestEngine
import pandas as pd
from datetime import date, timedelta
import strategy as strategies

# Setup
symbol = "NIFTY"
end_date = date.today()
start_date = end_date - timedelta(days=100)

print(f"Debugging History for {symbol} from {start_date} to {end_date}")

engine = BacktestEngine(symbol, start_date, end_date)
output = engine.run(strategies.get_all_strategies())

history = output['history']
trades = output['trades']

print(f"\nTotal Trades: {len(trades)}")

if history:
    df = pd.DataFrame(history)
    print("\n--- Market Regime History (First 20 rows) ---")
    print(df[['date', 'iv_bucket', 'trend_strength', 'tokens']].head(20).to_string())
    
    print("\n--- Value Counts ---")
    print("IV Buckets:")
    print(df['iv_bucket'].value_counts())
    print("\nTrend Strength:")
    print(df['trend_strength'].value_counts())
else:
    print("No History Generated (Data fetching issue?)")
