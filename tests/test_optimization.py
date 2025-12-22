import datetime
import os
import time
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from modules.api.data_loader import get_bhavcopy_data, DATA_DIR

def test_optimization():
    print("Testing Cache Optimization...")
    d = datetime.date(2024, 12, 19)
    date_str = d.strftime("%Y%m%d")
    csv_file = f"BhavCopy_NSE_FO_0_0_0_{date_str}_F_0000.csv"
    path = os.path.join(DATA_DIR, csv_file)
    
    # 1. First load: Might be raw (from internal state) or processed
    print("\n1. First Load (Migrating/Processing)...")
    start = time.time()
    get_bhavcopy_data(d, type='fo')
    print(f"Time taken: {time.time() - start:.4f}s")
    
    # Check if processed
    with open(path, 'r') as f:
        header = f.readline()
        if "INSTRUMENT" in header:
             print("SUCCESS: Cache file is now PROCESSED (contains INSTRUMENT).")
        else:
             print("FAILURE: Cache file is still RAW.")
             
    # 2. Second load: Should be INSTANT (reading processed file, no apply())
    print("\n2. Second Load (Using Processed Cache)...")
    start = time.time()
    get_bhavcopy_data(d, type='fo')
    duration = time.time() - start
    print(f"Time taken: {duration:.4f}s")
    
    if duration < 0.2:
        print("SUCCESS: Loading is extremely fast (< 0.2s).")
    else:
        print(f"WARNING: Loading still took {duration:.4f}s.")

test_optimization()
