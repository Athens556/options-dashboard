
import requests
import pandas as pd

def test_sensibull_ivp(symbol="NIFTY"):
    url = "https://oxide.sensibull.com/v1/compute/compute_intraday"
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    payload = {
        "underlying": symbol,
        "interval": "1D",
        "chart_keys": ["ivp", "iv"], 
        "client_atm_strikes_map": {},
        "offset": None,
        "update_atm": True
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            if 'payload' in data and 'chart_data' in data['payload']:
                chart_data = data['payload']['chart_data']
                print("Data keys for first entry:", list(chart_data.values())[0].keys())
                
                # Check random entry
                first_val = list(chart_data.values())[-1]
                print("Last Entry Data:", first_val)
                
                if 'ivp' in first_val:
                    print(f"IVP found: {first_val['ivp']}")
                else:
                    print("IVP NOT found in data.")
            else:
                print("No chart_data in payload.")
        else:
            print(f"Error: {response.status_code}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_sensibull_ivp()
