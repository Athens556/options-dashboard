
import data_loader
import pandas as pd

def test_fetch_nifty_fo_symbols():
    print("Testing fetch_nifty_fo_symbols...")
    symbols = data_loader.fetch_nifty_fo_symbols()
    
    if symbols:
        print(f"Success! Fetched {len(symbols)} symbols.")
        print(f"First 10 symbols: {symbols[:10]}")
        
        # Verify specific important symbols exist
        expected = ["NIFTY", "BANKNIFTY", "RELIANCE"]
        for sym in expected:
            if sym in symbols:
                print(f"Verified: {sym} is present.")
            else:
                print(f"Warning: {sym} is MISSING!")
    else:
        print("Failed to fetch symbols.")

if __name__ == "__main__":
    test_fetch_nifty_fo_symbols()
