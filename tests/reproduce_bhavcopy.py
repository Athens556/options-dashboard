import datetime
from data_loader import get_bhavcopy_data
import os
import pandas as pd

def test_date(d):
    print(f"Testing {d}...")
    try:
        df = get_bhavcopy_data(d, type='fo')
        if df is not None and not df.empty:
            print(f"Success: Retrieved {len(df)} records.")
            print("Columns:", list(df.columns))
            print("Sample Row:", df.iloc[0].to_dict())
            
            # Check for INSTRUMENT column if it's UDiFF date
            if 'INSTRUMENT' in df.columns:
                print("INSTRUMENT check: Passed")
            else:
                print("INSTRUMENT check: FAILED (Column missing)")
                
        else:
            print("Failed: Returned empty or None")
    except Exception as e:
        print(f"Failed with error: {e}")

# Jan 31, 2024 - Legacy (should verify existing logic still works)
print("\n--- Legacy Date ---")
test_date(datetime.date(2024, 1, 31))

# Dec 20, 2024 - UDiFF (The one that was failing)
print("\n--- UDiFF Date ---")
test_date(datetime.date(2024, 12, 20))
