import data_loader
from datetime import date
import pandas as pd

def test_nifty_fetch():
    print("Testing NIFTY Data Fetching...")
    symbol = "NIFTY"
    end_date = date(2024, 1, 10)
    start_date = date(2024, 1, 1)
    
    print(f"Fetching data for {symbol} from {start_date} to {end_date}...")
    
    try:
        data, error = data_loader.process_market_data(symbol, start_date, end_date)
        
        if error:
            print(f"Error: {error}")
        else:
            print("Data fetched successfully!")
            print(f"Spot Data: {len(data['spot'])} records")
            if not data['spot'].empty:
                print(data['spot'].head())
            
    except Exception as e:
        print(f"Exception occurred: {e}")

if __name__ == "__main__":
    test_nifty_fetch()
