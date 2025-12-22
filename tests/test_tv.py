from tvDatafeed import TvDatafeed, Interval
import pandas as pd

def test_tvdatafeed(symbol, exchange):
    print(f"Testing tvdatafeed for {exchange}:{symbol}...")
    
    # Initialize without credentials (guest mode)
    tv = TvDatafeed()
    
    try:
        # Fetch data
        df = tv.get_hist(symbol=symbol, exchange=exchange, interval=Interval.in_daily, n_bars=100)
        
        if df is not None and not df.empty:
            print(f"Fetched {len(df)} records.")
            print(df.head())
            print(df.tail())
        else:
            print("No data returned.")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_tvdatafeed("SBIN", "NSE")
    test_tvdatafeed("NIFTY", "NSE") # Check index
