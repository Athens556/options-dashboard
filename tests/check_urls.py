import requests
from datetime import date

def check_url(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    print(f"Checking {url}...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        if response.status_code == 200:
            print("HEAD of content:", response.content[:20])
            if b'html' in response.content[:20].lower():
                 print("It's HTML, not ZIP.")
            elif b'PK' in response.content[:20]:
                 print("It's a ZIP file!")
    except Exception as e:
        print(f"Error: {e}")

d = date(2024, 12, 20)
# Standard format: contract/historical/DERIVATIVES/YYYY/MMM/foDDMMMYYYYbhav.csv.zip
# Month is uppercase 3 letters.

month_str = d.strftime("%b").upper()
date_str = d.strftime("%d%b%Y").upper()

url1 = f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{d.year}/{month_str}/fo{date_str}bhav.csv.zip"
url2 = f"https://archives.nseindia.com/content/historical/DERIVATIVES/{d.year}/{month_str}/fo{date_str}bhav.csv.zip"
url3 = f"https://www.nseindia.com/content/historical/DERIVATIVES/{d.year}/{month_str}/fo{date_str}bhav.csv.zip"

check_url(url1)
check_url(url2)
check_url(url3)
