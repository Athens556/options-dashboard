import datetime
import os
import time
from data_loader import get_bhavcopy_data, DATA_DIR

def test_rate_limit():
    print("Testing Rate Limiting...")
    
    # Pick 2 recent dates to fetch
    dates = [
        datetime.date(2024, 12, 17),
        datetime.date(2024, 12, 18)
    ]
    
    # Clean cache for these dates to force download
    for d in dates:
        date_str = d.strftime("%Y%m%d")
        csv_file = f"BhavCopy_NSE_FO_0_0_0_{date_str}_F_0000.csv"
        path = os.path.join(DATA_DIR, csv_file)
        if os.path.exists(path):
            os.remove(path)
            
    start_time = time.time()
    
    for d in dates:
        print(f"Fetching {d}...")
        get_bhavcopy_data(d, type='fo')
        
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"Total time for {len(dates)} requests: {duration:.2f} seconds")
    avg_slowness = duration / len(dates)
    print(f"Average time per request: {avg_slowness:.2f} seconds")
    
    if avg_slowness >= 0.5:
        print("SUCCESS: Rate limiting active (>= 0.5s per request)")
    else:
        print("WARNING: Too fast! Rate limiting might not be working.")

test_rate_limit()
