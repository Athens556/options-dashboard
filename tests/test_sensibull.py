import requests
import json
import pandas as pd

def test_sensibull(symbol):
    url = "https://oxide.sensibull.com/v1/compute/compute_intraday"
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    payload = {
        "underlying": symbol,
        "interval": "1D",
        "chart_keys": [
            "multi_strategy",
            "oi_options",
            "oi_futures",
            "oi_change_options",
            "oi_change_futures",
            "pcr",
            "max_pain",
            "iv",
            "ivp",
            "rolling_atm_straddle",
            "indiavix"
        ],
        "client_atm_strikes_map": {},
        "offset": None,
        "update_atm": True
    }
    
    print(f"Fetching Sensibull data for {symbol}...")
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            # print(str(data)[:500]) # Print first 500 chars
            
            # Inspect keys
            if 'payload' in data:
                payload_data = data['payload']
                
                if 'chart_data' in payload_data:
                    chart_data = payload_data['chart_data']
                    keys = list(chart_data.keys())
                    print(f"Total Records: {len(keys)}")
                    if len(keys) > 0:
                        first_key = keys[0]
                        print(f"Sample Key: {first_key}")
                        print("Sample Data:", chart_data[first_key])
                else:
                    print("No 'chart_data' in payload.")
            else:
                print("No 'payload' key in response.")
        else:
            print("Error:", response.text)
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_sensibull("NIFTY")
    test_sensibull("SBIN")
