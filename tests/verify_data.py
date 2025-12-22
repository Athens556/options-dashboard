import data_loader
from datetime import date, timedelta
import pandas as pd

def test_data_loader():
    print("Testing Data Loader...")
    symbol = "SBIN"
    end_date = date(2024, 1, 10)
    start_date = date(2024, 1, 1)
    
    print(f"Fetching data for {symbol} from {start_date} to {end_date}...")
    
    try:
        data, error = data_loader.process_market_data(symbol, start_date, end_date)
        
        if error:
            print(f"Error: {error}")
            return
            
        print("Data fetched successfully!")
        print(f"Spot Data: {len(data['spot'])} records")
        print(f"VIX Data: {len(data['vix'])} records")
        print(f"RV Data: {len(data['rv'])} records")
        print(f"IV Data: {len(data['iv'])} records")
        
        if not data['iv'].empty:
            print("\nSample IV Data:")
            print(data['iv'].head())
        else:
            print("\nWARNING: IV Data is empty. Check if Bhavcopy was downloaded.")
            
    except Exception as e:
        print(f"Exception occurred: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_data_loader()
