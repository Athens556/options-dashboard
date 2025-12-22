import pandas as pd
from dhanhq import dhanhq
import dhan_config
import datetime

def test_historical_data():
    print("Testing DhanHQ Historical Data...")
    client_id = dhan_config.CLIENT_ID
    access_token = dhan_config.ACCESS_TOKEN
    
    dhan = dhanhq(client_id, access_token)
    
    # Test 1: SBIN (Equity)
    print("\n--- Testing SBIN (Equity) ---")
    # Need to look up Security ID first. 
    # For test, I'll search in the CSV if I can, or hardcode if I know it.
    # But better to use the lookup logic.
    
    try:
        csv_path = "security_id_list.csv"
        df = pd.read_csv(csv_path)
        
        # SBIN
        mask = (df['SEM_TRADING_SYMBOL'] == 'SBIN') & (df['SEM_EXM_EXCH_ID'] == 'NSE')
        row = df[mask]
        
        if not row.empty:
            sid = row.iloc[0]['SEM_SMST_SECURITY_ID']
            print(f"Found SBIN Security ID: {sid}")
            
            start_date = (datetime.date.today() - datetime.timedelta(days=10)).strftime("%Y-%m-%d")
            end_date = datetime.date.today().strftime("%Y-%m-%d")
            
            print(f"Fetching data from {start_date} to {end_date}")
            
            data = dhan.historical_daily_data(
                security_id=int(sid),
                exchange_segment="NSE_EQ",
                instrument_type="EQUITY",
                expiry_code=0,
                from_date=start_date,
                to_date=end_date
            )
            
            # Print structure
            if isinstance(data, dict):
                 print(f"Status: {data.get('status')}")
                 print(f"Response Keys: {data.keys()}")
                 if 'data' in data:
                     raw_data = data['data']
                     print(f"Data Type: {type(raw_data)}")
                     print(f"Data Length: {len(raw_data)}")
                     print(f"Raw Data (first 200 chars): {str(raw_data)[:200]}")
                     
                     if isinstance(raw_data, list) and len(raw_data) > 0:
                         print("First Record:", raw_data[0])
                     elif isinstance(raw_data, dict):
                         print("First Key:", list(raw_data.keys())[0])
                         print("First Value:", list(raw_data.values())[0])
            else:
                 print("Response:", data)
                 
        else:
            print("SBIN not found in CSV")

    except Exception as e:
        print(f"Error testing SBIN: {e}")
        import traceback
        traceback.print_exc()

    # Test 2: NIFTY 50 (Index)
    print("\n--- Testing NIFTY 50 (Index) ---")
    try:
        # NIFTY 50 symbol in Dhan CSV might be 'Nifty 50' or 'NIFTY'
        # Let's search loosely
        mask = df['SEM_TRADING_SYMBOL'].str.contains('Nifty 50', case=False, na=False)
        # Also check segment for Index? IDX
        # Usually indices are in NSE, ID = 13 (Nifty 50) commonly
        
        row = df[mask]
        if not row.empty:
            # print(row.head())
            # Usually we want the Index one
            # Let's try to find one with segment 'IDX' if column exists
            # Or just grab the first one
            sid = row.iloc[0]['SEM_SMST_SECURITY_ID']
            print(f"Found NIFTY Security ID: {sid}")
            
            start_date = (datetime.date.today() - datetime.timedelta(days=10)).strftime("%Y-%m-%d")
            end_date = datetime.date.today().strftime("%Y-%m-%d")
            
            data = dhan.historical_daily_data(
                security_id=int(sid),
                exchange_segment="IDX_I", 
                instrument_type="IDX_I",
                expiry_code=0,
                from_date=start_date,
                to_date=end_date
            )
             
            if isinstance(data, dict) and 'data' in data:
                 print(f"Data Records: {len(data['data'])}")
                 if len(data['data']) > 0:
                     print("First Record:", data['data'][0])
            else:
                 print("Response:", data)
        else:
             print("Nifty 50 not found via search")
             
    except Exception as e:
        print(f"Error testing NIFTY: {e}")

if __name__ == "__main__":
    test_historical_data()
