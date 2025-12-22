import sys
import os
import pandas as pd
from dhanhq import dhanhq
import dhan_config

def test_security_list():
    print("Testing DhanHQ Security List...")
    client_id = dhan_config.CLIENT_ID
    access_token = dhan_config.ACCESS_TOKEN
    
    try:
        dhan = dhanhq(client_id, access_token)
        print("Dhan Object Created")
        
        # Test fetch_security_list
        print("Help on fetch_security_list:")
        try:
             help(dhan.fetch_security_list)
        except:
             print("No help available")

        print("Calling fetch_security_list with no args...")
        res = dhan.fetch_security_list()
        print("Result Type:", type(res))
        if isinstance(res, pd.DataFrame):
             print(res.head())
        else:
             print("Result:", res)

        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_security_list()
