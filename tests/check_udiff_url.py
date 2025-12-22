import requests
from datetime import date
import time

def check_url(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://www.nseindia.com/"
    }
    print(f"Checking {url}...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("Success! It's valid.")
            return True
    except Exception as e:
        print(f"Error: {e}")
    return False

d = date(2024, 12, 20)
date_str = d.strftime("%Y%m%d") # 20241220
year = str(d.year)
month_str = d.strftime("%b").upper() # DEC

filename = f"BhavCopy_NSE_FO_0_0_0_{date_str}_F_0000.csv.zip"

urls = [
    f"https://nsearchives.nseindia.com/content/fo/{filename}",
    f"https://archives.nseindia.com/content/fo/{filename}",
    f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{year}/{month_str}/{filename}",
    f"https://archives.nseindia.com/content/historical/DERIVATIVES/{filename}", # unlikely but trying
    f"https://www.nseindia.com/AllReports/Derivatives/{filename}"
]

for url in urls:
    if check_url(url):
        break
    time.sleep(1)
