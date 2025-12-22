import requests
import pandas as pd

API_KEY = "sk-live-VrBVAfOVG65kGKovMvJXnDkTjVvYJAMZDuqJ4oMv"
BASE_URL = "https://stock.indianapi.in"

def test_indianapi_fetch(symbol):
    print(f"Testing IndianAPI.in for {symbol}...")
    
    # Endpoint based on search results
    url = f"{BASE_URL}/historical_data"
    
    params = {
        "stock_name": symbol,
        "period": "1yr",
        "filter": "price"
    }
    
    headers = {
        "X-Api-Key": API_KEY
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Response Keys:", data.keys())
            print("Raw Data (first 200 chars):", str(data)[:200])
            
            # Try to infer structure
            if 'datasets' in data:
                 print("Datasets found.")
            else:
                 print("No datasets key.")
        else:
            print("Error:", response.text)
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_indianapi_fetch("SBIN")
