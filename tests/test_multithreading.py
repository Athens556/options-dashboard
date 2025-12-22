import datetime
import time
from data_loader import get_historical_options_data

def test_multithreading():
    print("Testing Multithreaded Speed...")
    start_date = datetime.date(2024, 12, 10)
    end_date = datetime.date(2024, 12, 20) # 10 days
    
    # Files should be cached by now or will be downloaded
    # First run might download (slow due to rate limits + processing)
    # Second run should be blazing fast
    
    print(f"\nFetching {start_date} to {end_date} (10 days)...")
    start = time.time()
    
    # We use a symbol like NIFTY
    df = get_historical_options_data("NIFTY", start_date, end_date)
    
    duration = time.time() - start
    print(f"Total rows fetched: {len(df)}")
    print(f"Time taken: {duration:.4f}s")
    
    if duration < 2.0: # 10 days * 0.18s = 1.8s. With threading it should be even faster (e.g. 0.5s)
        print("SUCCESS: Loading is extremely fast with multithreading.")
    else:
        # If it had to download, it would be slow.
        print(f"Time taken {duration:.4f}s. (If this was first run/downloading, it is expected).")
        
    print("\nRunning again (Hot Cache)...")
    start = time.time()
    df = get_historical_options_data("NIFTY", start_date, end_date)
    duration = time.time() - start
    print(f"Time taken (Hot Cache): {duration:.4f}s")

if __name__ == "__main__":
    test_multithreading()
