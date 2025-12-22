from datetime import date
from data_loader import get_india_vix
import pandas as pd

def test_vix_fix():
    print("Testing India VIX (Bhavcopy Source)...")
    start = date(2024, 12, 1)
    end = date(2024, 12, 31)
    
    # This should use cached files or download Index Bhavcopy
    vix_series = get_india_vix(start, end)
    
    print("\nResult:")
    print(vix_series)
    
    if not vix_series.empty:
        print("SUCCESS: VIX data fetched.")
        # Check last value
        print(f"Latest VIX: {vix_series.iloc[-1]}")
    else:
        print("FAILURE: VIX data empty.")

test_vix_fix()
