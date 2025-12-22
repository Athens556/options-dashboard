import datetime
import os
from data_loader import get_bhavcopy_data, DATA_DIR

def test_cache(d):
    print(f"\nTesting {d}...")
    
    # Expected filename based on new logic
    date_str = d.strftime("%Y%m%d")
    expected_file = f"BhavCopy_NSE_FO_0_0_0_{date_str}_F_0000.csv"
    expected_path = os.path.join(DATA_DIR, expected_file)
    
    if os.path.exists(expected_path):
        print("Pre-cleaning: Removing existing cache file for clean test.")
        os.remove(expected_path)
    
    # Run fetch
    print("Fetching data (should trigger download)...")
    get_bhavcopy_data(d, type='fo')
    
    # Check if saved
    if os.path.exists(expected_path):
        print(f"SUCCESS: File saved to {expected_path}")
        # Verify size/content
        print(f"File size: {os.path.getsize(expected_path)} bytes")
        
        # Run fetch again (should be fast/from cache)
        print("Fetching again (should use cache)...")
        get_bhavcopy_data(d, type='fo')
        print("Second fetch done.")
        
    else:
        print(f"FAILURE: File not found at {expected_path}")

# Test with a recent date
test_cache(datetime.date(2024, 12, 19))
