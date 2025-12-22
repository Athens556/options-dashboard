import yfinance as yf
import pandas as pd
from datetime import datetime

def test_vix():
    print("Testing India VIX Fetching...")
    # Recent dates
    start = "2024-12-01"
    end = "2024-12-20"
    
    ticker = "INDIAVIX.NS"
    print(f"Downloading {ticker} from {start} to {end}...")
    
    try:
        df = yf.download(ticker, start=start, end=end, progress=False)
        print("Data Downloaded:")
        print(df)
        
        if df.empty:
            print("FAILURE: DataFrame is empty.")
        else:
            print("SUCCESS: Data retrieved.")
            
    except Exception as e:
        print(f"EXCEPTION: {e}")

test_vix()
