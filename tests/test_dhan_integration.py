import data_loader
import pandas as pd
from datetime import date, timedelta

def test_integration():
    print("Testing DhanHQ Integration...")
    
    symbol = "SBIN"
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    print(f"Fetching data for {symbol} from {start_date} to {end_date}...")
    
    try:
        df = data_loader.fetch_dhan_data(symbol, start_date, end_date)
        
        if df.empty:
            print("FAILED: No data returned.")
        else:
            print(f"SUCCESS: Fetched {len(df)} records.")
            print(df.head())
            print(df.tail())
            
            # Verify columns
            expected_cols = ['close'] # open, high, low might be there but close is critical
            if 'close' in df.columns:
                print("SUCCESS: 'close' column found.")
            else:
                print(f"FAILED: 'close' column missing. Columns: {df.columns}")
                
            # Verify Index is Datetime
            if isinstance(df.index, pd.DatetimeIndex):
                 print("SUCCESS: Index is DatetimeIndex.")
            else:
                 print(f"FAILED: Index is {type(df.index)}")
                 
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_integration()
