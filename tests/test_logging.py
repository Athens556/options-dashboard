import datetime
import os
import io
import sys
from data_loader import get_bhavcopy_data, DATA_DIR

def test_logging():
    print("Testing Logging Output...")
    d = datetime.date(2024, 12, 19)
    date_str = d.strftime("%Y%m%d")
    csv_file = f"BhavCopy_NSE_FO_0_0_0_{date_str}_F_0000.csv"
    
    # 1. Fetch (Should be cache hit)
    print("\n[ACTION] Triggering Cache Hit:")
    get_bhavcopy_data(d, type='fo')
    
    # 2. Fetch (Should be miss if we define new date or delete)
    # Let's delete to force miss
    path = os.path.join(DATA_DIR, csv_file)
    if os.path.exists(path):
        os.remove(path)
        
    print("\n[ACTION] Triggering Cache Miss (Download + Save):")
    get_bhavcopy_data(d, type='fo')

test_logging()
