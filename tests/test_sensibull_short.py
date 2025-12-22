import requests
import json
import pandas as pd

def test_sensibull_short(symbol):
    url = "https://oxide.sensibull.com/v1/compute/compute_intraday"
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Using the SHORT list of keys as in data_loader.py
    payload = {
        "underlying": symbol,
        "interval": "1D",
        "chart_keys": ["iv", "indiavix", "ivp"], 
        "client_atm_strikes_map": {},
        "offset": None,
        "update_atm": True
    }
    
    print(f"Fetching Sensibull data for {symbol} (Short Keys)...")
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'payload' in data and 'chart_data' in data['payload']:
                chart_data = data['payload']['chart_data']
                print(f"Records found: {len(chart_data)}")
            else:
                print("No chart_data found.")
                print("Response keys:", data.keys())
                if 'payload' in data:
                    print("Payload keys:", data['payload'].keys())
        else:
            print("Error:", response.text)
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_sensibull_short("NIFTY")
    test_sensibull_short("SBIN")
