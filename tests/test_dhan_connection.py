import sys
import os
import pandas as pd
from dhanhq import dhanhq
import dhan_config

def test_dhan():
    print("Testing DhanHQ Integration...")
    client_id = dhan_config.CLIENT_ID
    access_token = dhan_config.ACCESS_TOKEN
    
    try:
        dhan = dhanhq(client_id, access_token)
        print("Dhan Object Created")
    except Exception as e:
        print(f"Error creating Dhan object: {e}")
        return

    # Try fetching a simple equity symbol, e.g., SBIN
    # reliable Security IDs: SBIN-NSE-EQ: 3045, Nifty 50: 13
    # We need to solve the Security ID mapping problem. 
    # For this test I will use a known ID.
    
    # 13 is Nifty 50 Index on NSE
    security_id_nifty = "13" 
    exchange_segment = "NSE_IND" # or NSE_FNO, NSE_EQ
    instrument_type = "INDEX"
    
    print(f"Fetching data for Nifty 50 (ID: {security_id_nifty})...")
    
    try:
        # Historical Data
        print("Testing historical_daily_data w/ NSE...")
        # Note: security_id for NIFTY 50 might need to be verified.
        # Assuming 13 is correct for test or we just see if it accepts it.
        # For historical_daily_data, the arguments might be:
        # security_id, exchange_segment, instrument_type, from_date, to_date
        
        data = dhan.historical_daily_data(
            security_id="13", 
            exchange_segment=dhan.NSE, 
            instrument_type=dhan.INDEX,
            expiry_code=0,
            from_date="2024-01-01",
            to_date="2024-01-05"
        )
        
        print("Data Response Type:", type(data))
        if isinstance(data, dict):
            if 'data' in data:
                print(f"Received {len(data['data'])} records")
                print(data['data'][:2])
            else:
                print("No 'data' field in response:", data.keys())
                print(data)
        else:
             print("Response:", data)

        print("Testing fetch_security_list...")
        # sec_list = dhan.fetch_security_list(mode='compact', exchange='NSE') 
        # print("Security List Result:", sec_list)
        # It seems fetch_security_list is NOT available in dir(dhan) from previous run?
        # previous dir(dhan): [..., 'fetch_security_list', ...] -> YES IT IS THERE.
        
        dhan.fetch_security_list(mode='compact', exchange_segment='NSE')
        print("Security List fetched (check if file created or returned)")

             
    except Exception as e:
        print(f"Error fetching data: {e}")

if __name__ == "__main__":
    test_dhan()
