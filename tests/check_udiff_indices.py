import requests
import pandas as pd
import io
import zipfile

def check_indices():
    # URL confirmed in previous step
    url = "https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_20241220_F_0000.csv.zip"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://www.nseindia.com/"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            csv_filename = z.namelist()[0]
            with z.open(csv_filename) as f:
                df = pd.read_csv(f)
                
                # Check unique TckrSymb where FinInstrmTp might suggest Index
                # Or just print unique TckrSymb that look like NIFTY
                
                nifty_rows = df[df['TckrSymb'].str.contains('NIFTY', na=False)]
                print("Unique NIFTY symbols:", nifty_rows['TckrSymb'].unique())
                
                # Check OptnTp for Futures
                futures = df[df['OptnTp'].isna() | (df['OptnTp'] == "")]
                if not futures.empty:
                    print("Futures OptnTp sample:", futures['OptnTp'].unique())
                else:
                    # Maybe it's not empty/NaN but something else?
                    print("OptnTp values:", df['OptnTp'].unique())

if __name__ == "__main__":
    check_indices()
