import data_loader
from datetime import date, timedelta
import pandas as pd

def test_recent_fetch():
    print("Testing Recent Data Fetching...")
    symbol = "NIFTY"
    today = date.today()
    # Try fetching for the last 7 days
    start_date = today - timedelta(days=7)
    end_date = today
    
    print(f"Fetching data for {symbol} from {start_date} to {end_date}...")
    
    try:
        data, error = data_loader.process_market_data(symbol, start_date, end_date)
        
        if error:
            print(f"Error: {error}")
        else:
            print(f"Data fetched successfully! Source: {data.get('source')}")
            print(f"Spot Data: {len(data['spot'])} records")
            if not data['spot'].empty:
                print(data['spot'].tail())
            else:
                print("Spot data is empty despite success?")
            
    except Exception as e:
        print(f"Exception occurred: {e}")

if __name__ == "__main__":
    test_recent_fetch()
