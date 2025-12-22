import datetime
from data_loader import get_bhavcopy_data, get_udiff_bhavcopy_data
import time

def test_cache_and_future():
    print("--- Test 1: Future Date Blocking ---")
    future_date = datetime.date(2025, 12, 25)
    print(f"Requesting data for future date: {future_date}")
    # Should return None and NOT print 'Fetching...' or errors
    res = get_udiff_bhavcopy_data(future_date)
    if res is None:
        print("SUCCESS: Future date returned None immediately.")
    else:
        print("FAILURE: Future date returned something or tried to fetch.")
        
    print("\n--- Test 2: LRU Cache Optimization ---")
    # Use a recent past date that definitely exists
    past_date = datetime.date(2024, 12, 18)
    
    print("Call 1 (Should hit disk cache and log 'File is cache hit'):")
    df1 = get_bhavcopy_data(past_date)
    
    print("Call 2 (Should be SILENT - Memory Cache Hit):")
    df2 = get_bhavcopy_data(past_date)
    
    print("Call 3 (Should be SILENT - Memory Cache Hit):")
    df3 = get_bhavcopy_data(past_date)
    
    if df1 is not None and df2 is not None:
        print(f"Rows: {len(df1)}")
        print("SUCCESS: Data retrieved multiple times.")
    else:
        print("FAILURE: Data not retrieved.")

if __name__ == "__main__":
    test_cache_and_future()
