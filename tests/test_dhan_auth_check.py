from dhanhq import dhanhq
import dhan_config
import pandas as pd

def test_dummy_auth():
    print("\n--- Testing fetch_security_list with DUMMY credentials ---")
    try:
        dhan = dhanhq("DUMMY_ID", "DUMMY_TOKEN")
        # Ensure we don't just read from existing file, force fresh fetch if possible?
        # The library saves to file.
        res = dhan.fetch_security_list()
        print("Result with DUMMY creds:", type(res))
    except Exception as e:
        print(f"DUMMY creds failed: {e}")

def test_private_api():
    print("\n--- Testing Private API (Funds/Holdings) ---")
    try:
        dhan = dhanhq(dhan_config.CLIENT_ID, dhan_config.ACCESS_TOKEN)
        # get_fund_limits() or get_holdings()
        print("Fetching Fund Limits...")
        res = dhan.get_fund_limits()
        print("Fund Limits Result:", res)
        
        if isinstance(res, dict) and res.get('status') == 'failure':
             print("Fund Limits Status: FAILURE")
             
    except Exception as e:
        print(f"Private API Error: {e}")

if __name__ == "__main__":
    test_dummy_auth()
    test_private_api()
