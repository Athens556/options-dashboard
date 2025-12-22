import requests
import pandas as pd
import io
import zipfile

def inspect_data():
    url = "https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_20241220_F_0000.csv.zip"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://www.nseindia.com/"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            print("Files in zip:", z.namelist())
            csv_filename = z.namelist()[0]
            with z.open(csv_filename) as f:
                df = pd.read_csv(f)
                print("\nColumns:", list(df.columns))
                print("\nFirst row:", df.iloc[0].to_dict())
    else:
        print("Failed to download")

if __name__ == "__main__":
    inspect_data()
