import requests
import pandas as pd
import io

def check_url():
    url = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print("Success! Content preview:")
            print(response.text[:200])
            
            # Try parsing
            df = pd.read_csv(io.StringIO(response.text))
            print("\nColumns:", df.columns)
            print("\nFirst 5 rows:")
            print(df.head())
            return df
        else:
            print(f"Failed with status code: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_url()
