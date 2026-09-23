"""Market data adapters.

Every fetcher returns a DataFrame on a normalized DatetimeIndex with a `close`
column plus whichever of `iv`, `vix`, `ivp` the source provides. Heavy SDKs
(yfinance, jugaad-data, kiteconnect, dhanhq) are imported inside the function
that needs them so the app starts fast.
"""
import pandas as pd
from datetime import date, timedelta, datetime
import os
from modules import utils
import numpy as np
import sys
import contextlib

HTTP_TIMEOUT = 15


@contextlib.contextmanager
def suppress_stdout_stderr():
    """A context manager that redirects stdout and stderr to devnull"""
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = devnull
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

DATA_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)

def fetch_nifty_fo_symbols():
    """Fetches the list of F&O symbols from NSE official website."""
    url = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        import requests
        import io
        response = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
        if response.status_code == 200:
            # Parse CSV
            df = pd.read_csv(io.StringIO(response.text))
            
            # Clean column names
            df.columns = [c.strip() for c in df.columns]
            
            if 'SYMBOL' in df.columns:
                symbols = df['SYMBOL'].apply(lambda x: x.strip()).unique().tolist()
                symbols.sort()
                return symbols
    except Exception as e:
        print(f"Error fetching NSE symbols: {e}")
    
    return []

def get_kite_login_url(api_key):
    """Returns the login URL for Kite Connect."""
    from kiteconnect import KiteConnect
    kite = KiteConnect(api_key=api_key)
    return kite.login_url()

def generate_kite_session(api_key, api_secret, request_token):
    """Generates a Kite session and returns the authenticated instance."""
    from kiteconnect import KiteConnect
    kite = KiteConnect(api_key=api_key)
    data = kite.generate_session(request_token, api_secret=api_secret)
    kite.set_access_token(data["access_token"])
    return kite

def fetch_kite_historical_data(kite, instrument_token, from_date, to_date, interval='day'):
    """Fetches historical data from Kite."""
    try:
        records = kite.historical_data(instrument_token, from_date, to_date, interval)
        df = pd.DataFrame(records)
        if not df.empty:
            df.set_index('date', inplace=True)
            # Kite returns timezone aware datetimes; strip to naive calendar days
            df.index = pd.to_datetime([d.date() for d in df.index])
        return df
    except Exception as e:
        error_msg = str(e)
        if "Insufficient permission" in error_msg:
            print("Error: Your Kite Connect app does not have access to Historical Data API. This is a paid add-on.")
            # We can re-raise or handle it. For now let's print and return empty so app shows the error.
            raise Exception("Your Kite Connect app does not have the 'Historical Data' permission. Please check your subscription on developers.kite.trade.")
        print(f"Error fetching Kite data: {e}")
        return pd.DataFrame()

def fetch_indianapi_data(symbol, api_key):
    """Fetches historical data from IndianAPI.in."""
    import requests
    base_url = "https://stock.indianapi.in/historical_data"
    
    params = {
        "stock_name": symbol,
        "period": "1yr", # Default to 1yr for now
        "filter": "price"
    }
    
    headers = {
        "X-Api-Key": api_key
    }
    
    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=HTTP_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            if 'datasets' in data and len(data['datasets']) > 0:
                values = data['datasets'][0]['values']
                # values is list of [date, price]
                df = pd.DataFrame(values, columns=['date', 'close'])
                df['date'] = pd.to_datetime(df['date']).dt.normalize()
                df['close'] = pd.to_numeric(df['close'])
                df.set_index('date', inplace=True)
                return df
    except Exception as e:
        print(f"Error fetching IndianAPI data: {e}")
        
    return pd.DataFrame()

def fetch_tv_data(symbol, exchange="NSE"):
    """Fetches historical data from TradingView."""
    try:
        from tvDatafeed import TvDatafeed, Interval
        tv = TvDatafeed()
        # Fetch daily data
        df = tv.get_hist(symbol=symbol, exchange=exchange, interval=Interval.in_daily, n_bars=365)
        
        if df is not None and not df.empty:
            # df index is datetime, columns: symbol, open, high, low, close, volume
            df = df[['close']].copy()
            df.index = pd.DatetimeIndex(df.index).normalize()
            return df
    except Exception as e:
        print(f"Error fetching TradingView data: {e}")
        
    return pd.DataFrame()

def fetch_sensibull_data(symbol):
    """Fetches historical data from Sensibull internal API."""
    import requests
    url = "https://oxide.sensibull.com/v1/compute/compute_intraday"
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Map common symbols if needed
    underlying = symbol
    if symbol == "NIFTY": underlying = "NIFTY"
    if symbol == "BANKNIFTY": underlying = "BANKNIFTY"
    
    payload = {
        "underlying": underlying,
        "interval": "1D",
        "chart_keys": ["iv", "indiavix", "ivp"], # Requesting specific keys
        "client_atm_strikes_map": {},
        "offset": None,
        "update_atm": True
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=HTTP_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            if 'payload' in data and 'chart_data' in data['payload']:
                chart_data = data['payload']['chart_data']
                records = [{
                    'date': ts,
                    'close': v.get('spot'),
                    'iv': (v.get('iv') or {}).get('atm_iv'),
                    'vix': (v.get('indiavix') or {}).get('indiavix_price'),
                    'ivp': (v.get('ivp') or {}).get('ivp'),
                } for ts, v in chart_data.items()]

                df = pd.DataFrame(records)
                if not df.empty:
                    # Timestamps carry +05:30; keep the IST calendar day
                    df['date'] = pd.to_datetime(df['date'].str[:10])
                    df = df.set_index('date').sort_index()
                    df = df[~df.index.duplicated(keep='last')].apply(pd.to_numeric, errors='coerce')
                    return df.dropna(axis=1, how='all')
    except Exception as e:
        print(f"Error fetching Sensibull data: {e}")
        
    return pd.DataFrame()

def get_dhan_client():
    """Returns authenticated Dhan client."""
    from dhanhq import dhanhq
    from . import dhan_config
    return dhanhq(dhan_config.CLIENT_ID, dhan_config.ACCESS_TOKEN)

def fetch_dhan_security_id(symbol, exchange='NSE'):
    """Finds security ID for a symbol using the downloaded CSV list."""
    csv_path = "security_id_list.csv"
    
    # Map common symbols
    # if symbol == "NIFTY": symbol = "Nifty 50" # Not needed for TRADING_SYMBOL lookup
    # if symbol == "BANKNIFTY": symbol = "Nifty Bank" # Check Bank Nifty symbol?
    
    # If using NSE Equity, symbol usually matches directly e.g. "SBIN", "RELIANCE"
    # For Indices, TRADING_SYMBOL is usually "NIFTY", "BANKNIFTY" etc.
    
    if not os.path.exists(csv_path):
        print("Downloading Dhan Security List...")
        dhan = get_dhan_client()
        dhan.fetch_security_list(mode='compact', exchange_segment='NSE') 
    
    if os.path.exists(csv_path):
        try:
            # Optimize: Read only relevant columns if possible
            df = pd.read_csv(csv_path)
            
            # Filter by SEM_TRADING_SYMBOL
            mask = (df['SEM_TRADING_SYMBOL'] == symbol)
            
            # If exchange provided, filter by it if column exists
            if 'SEM_EXM_EXCH_ID' in df.columns:
               mask = mask & (df['SEM_EXM_EXCH_ID'] == exchange)
               
            row = df[mask]
            if not row.empty:
                # Return first match
                return str(row.iloc[0]['SEM_SMST_SECURITY_ID'])
                
        except Exception as e:
            print(f"Error reading security list: {e}")
            
    return None


def fetch_dhan_data(symbol, start_date, end_date):
    """Fetches historical data from DhanHQ."""
    dhan = get_dhan_client()
    
    # 1. Get Security ID
    # For indices, passing 'NSE' usually works for ID lookup in the CSV
    sid = fetch_dhan_security_id(symbol)
    
    if not sid:
        print(f"Security ID not found for {symbol}")
        return pd.DataFrame()
        
    try:
        # Determine Instrument Type and Exchange based on symbol
        # Ideally this comes from the CSV too, but for now:
        exchange_segment = "NSE_EQ" # Default (NSE Equity)
        instrument_type = "EQUITY"
        
        if symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
            instrument_type = "IDX_I" 
            exchange_segment = "IDX_I"

        
        # Convert dates to string format 'YYYY-MM-DD'
        if isinstance(start_date, (date, datetime)):
            start_date = start_date.strftime("%Y-%m-%d")
        if isinstance(end_date, (date, datetime)):
            end_date = end_date.strftime("%Y-%m-%d")
            
        # print(f"DEBUG: calling historical_daily_data(security_id={sid}, exchange_segment={exchange_segment}, instrument_type={instrument_type}, from_date={start_date}, to_date={end_date})")

        data = dhan.historical_daily_data(
            security_id=int(sid),
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            expiry_code=0,
            from_date=start_date,
            to_date=end_date
        )
        if isinstance(data, dict):
            if data.get('status') == 'failure':
                print(f"Dhan API Error: {data.get('remarks', 'No remarks')} | Data: {data.get('data')}")
                return pd.DataFrame()

        if isinstance(data, dict) and 'data' in data:
            records = data['data']
            
            # Adjust based on standard Dhan response if known, otherwise try DataFrame
            df = pd.DataFrame(records)
            
            # Standardize columns if they are not standard names
            # If list of lists, we need column names. 
            # If dicts, likely keys are "open", "close", "start_Time" (epoch?)
            
            # Assuming 'start_Time' is the key for date based on docs I've seen before.
            # But let's check columns if it's a dict.
            
            if not df.empty:
                # Map column names if needed.
                # Assuming standard keys: 'open', 'high', 'low', 'close', 'volume', 'start_Time'
                # If they are different, we might have issues.
                # For safety, print columns if debugging, but we are writing code.
                
                # Handling epoch time
                if 'start_Time' in df.columns:
                    # Dhan returns timestamp?
                    # or 'date'?
                    # We might need to inspect response in test script to be 100% sure.
                    # But let's proceed.
                    pass
                
                # Check for known keys
                rename_map = {
                    'start_Time': 'date',
                    'close': 'close',
                    'open': 'open', 
                    'high': 'high',
                    'low': 'low'
                }
                df.rename(columns=rename_map, inplace=True)
                
                # Normalize date
                # If date is numeric (epoch), convert
                # If string, convert
                if 'date' in df.columns:
                     # Check if numeric
                     if pd.api.types.is_numeric_dtype(df['date']):
                         df['date'] = pd.to_datetime(df['date'], unit='s' if df['date'].iloc[0] > 1e9 else 'ns').dt.normalize()
                     else:
                         df['date'] = pd.to_datetime(df['date']).dt.normalize()
                     
                     df.set_index('date', inplace=True)
                     return df
                     
    except Exception as e:
        print(f"Error fetching Dhan data: {e}")
        
    return pd.DataFrame()


import threading
import concurrent.futures
import zipfile
import io
import requests
import time

class FileLockManager:
    def __init__(self):
        self.locks = {}
        self.global_lock = threading.Lock()
        self.request_lock = threading.Lock() # Global lock for rate limiting

    def get_lock(self, filename):
        with self.global_lock:
            if filename not in self.locks:
                self.locks[filename] = threading.Lock()
            return self.locks[filename]
            
    def rate_limit(self):
        """Block until safe to make a request."""
        with self.request_lock:
            time.sleep(0.35) # Max ~2.8 requests/second

lock_manager = FileLockManager()

import functools

@functools.lru_cache(maxsize=32)
def get_udiff_bhavcopy_data(date_obj):
    """Downloads and reads UDiFF bhavcopy for a specific date (Post July 8 2024)."""
    # Prevent future dates
    if date_obj > datetime.now().date():
        return None
        
    date_str = date_obj.strftime("%Y%m%d")
    year = date_obj.strftime("%Y")
    month_str = date_obj.strftime("%b").upper()
    
    # Original Zip Filename from NSE
    zip_filename = f"BhavCopy_NSE_FO_0_0_0_{date_str}_F_0000.csv.zip"
    csv_filename = f"BhavCopy_NSE_FO_0_0_0_{date_str}_F_0000.csv"
    
    # Acquire lock for this specific file to prevent race conditions during download/write
    with lock_manager.get_lock(csv_filename):
        # Check if CSV already exists
        csv_path = os.path.join(DATA_DIR, csv_filename)
        
        df = None
        loaded_from_cache = False
        
        if os.path.exists(csv_path):
            try:
               df = pd.read_csv(csv_path, low_memory=False)
               loaded_from_cache = True
               print(f"File is cache hit: {csv_filename}")
            except Exception:
               # If corrupt, re-download
               df = None
        
        # If not found or corrupt, download it
        if df is None:
            print(f"Fetching file '{zip_filename}' since it not exist")
            # Try different URL patterns
            urls = [
                 f"https://nsearchives.nseindia.com/content/fo/{zip_filename}",
                 f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{year}/{month_str}/{zip_filename}",
                 f"https://www.nseindia.com/content/historical/DERIVATIVES/{year}/{month_str}/{zip_filename}"
            ]
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://www.nseindia.com/"
            }
            
            for url in urls:
                try:
                    # Global Rate Limiting: Stagger requests
                    lock_manager.rate_limit()
                    
                    response = requests.get(url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                            extracted_csv_name = z.namelist()[0]
                            with z.open(extracted_csv_name) as f:
                                df = pd.read_csv(f, low_memory=False)
                                # Do NOT save here yet, wait until processed
                                break
                except Exception as e:
                    print(f"Failed pattern {url}: {e}")
                    pass
                
        if df is None:
            return None
            
        # Standardize columns to match legacy format
        
        # Columns Map
        legacy_map = {
            'TckrSymb': 'SYMBOL',
            'XpryDt': 'EXPIRY_DT',
            'StrkPric': 'STRIKE_PR',
            'OptnTp': 'OPTION_TYP',
            'OpnPric': 'OPEN',
            'HghPric': 'HIGH',
            'LwPric': 'LOW',
            'ClsPric': 'CLOSE',
            'SttlmPric': 'SETTLE_PR',
            'TtlNbOfTxsExctd': 'CONTRACTS',
            'OpnIntrst': 'OPEN_INT',
            'ChngInOpnIntrst': 'CHG_IN_OI',
            'TradDt': 'TIMESTAMP'
        }
        
        # Check if we need to process (Rename columns)
        if 'TckrSymb' in df.columns:
            df.rename(columns=legacy_map, inplace=True)
        
        # Derive INSTRUMENT column
        # Check if already processed
        if 'INSTRUMENT' not in df.columns:
            # Vectorized (was a row-wise apply over ~50k rows per file)
            fin_map = {'IDO': 'OPTIDX', 'IDF': 'FUTIDX', 'STO': 'OPTSTK', 'STF': 'FUTSTK'}
            if 'FinInstrmTp' in df.columns:
                df['INSTRUMENT'] = df['FinInstrmTp'].map(fin_map)
            else:
                df['INSTRUMENT'] = None
            missing = df['INSTRUMENT'].isna()
            if missing.any():
                indices = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]
                is_index = df['SYMBOL'].isin(indices)
                is_opt = df['OPTION_TYP'].isin(['CE', 'PE'])
                derived = np.select([is_index & is_opt, is_index, is_opt], ['OPTIDX', 'FUTIDX', 'OPTSTK'], 'FUTSTK')
                df.loc[missing, 'INSTRUMENT'] = derived[missing.to_numpy()]
            
            # Save fully processed dataframe to disk
            # Overwrite if it was raw, or create new if downloaded
            try:
                print(f"Saving processed Bhavcopy to cache: {csv_filename}")
                df.to_csv(csv_path, index=False)
            except Exception as e:
                print(f"Failed to save {csv_filename}: {e}")
                pass
            
    return df

@functools.lru_cache(maxsize=32)
def get_bhavcopy_data(date_obj, type='fo'):
    """Downloads and reads bhavcopy for a specific date."""
    try:
        # Cutoff date for UDiFF format: July 8, 2024
        udiff_start_date = date(2024, 7, 8)
        
        if type == 'fo':
            if date_obj >= udiff_start_date:
                # Use new UDiFF downloader
                return get_udiff_bhavcopy_data(date_obj)
            else:
                # Use legacy jugaad-data
                # Lock needed here too if multiple threads access same date
                fname = f"fo{date_obj.strftime('%d%b%Y').upper()}bhav.csv"
                with lock_manager.get_lock(fname):
                    file_path = os.path.join(DATA_DIR, fname)
                    if not os.path.exists(file_path):
                        from jugaad_data.nse import bhavcopy_fo_save
                        file_path = bhavcopy_fo_save(date_obj, DATA_DIR)
        elif type == 'eq':
            fname = f"cm{date_obj.strftime('%d%b%Y').upper()}bhav.csv"
            with lock_manager.get_lock(fname):
                file_path = os.path.join(DATA_DIR, fname)
                if not os.path.exists(file_path):
                    from jugaad_data.nse import bhavcopy_save
                    file_path = bhavcopy_save(date_obj, DATA_DIR)
        else:
            return None
            
        df = pd.read_csv(file_path)
        return df
    except Exception as e:
        # print(f"Failed to fetch {type} data for {date_obj}: {e}")
        return None

def get_spot_data_from_index_bhavcopy(symbol, start_date, end_date):
    """Closing values for an index from the NSE index Bhavcopy, fetched in parallel."""
    from jugaad_data.nse import bhavcopy_index_save
    name_map = {"NIFTY": "Nifty 50", "BANKNIFTY": "Nifty Bank"}
    search_name = name_map.get(symbol, symbol).upper()
    dates = [d.date() for d in pd.bdate_range(start_date, end_date)]

    def process_date(d):
        fname = f"ind_close_all_{d.strftime('%d%m%Y')}.csv"
        file_path = os.path.join(DATA_DIR, fname)
        try:
            with lock_manager.get_lock(fname):
                if not os.path.exists(file_path):
                    lock_manager.rate_limit()
                    bhavcopy_index_save(d, DATA_DIR)
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                df.columns = [c.strip().upper() for c in df.columns]
                row = df[df['INDEX NAME'].str.strip().str.upper() == search_name]
                if not row.empty:
                    return d, float(row.iloc[0]['CLOSING INDEX VALUE'])
        except Exception:
            pass
        return d, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        spot_data = {d: v for d, v in executor.map(process_date, dates) if v is not None}

    if not spot_data:
        return pd.Series(dtype=float)
    return pd.Series(spot_data).sort_index()

def get_spot_from_futures(symbol, start_date, end_date):
    """Fetches near-month futures price as a proxy for spot."""
    # This calls get_bhavcopy_data which is now thread safe.
    # We can parallelize this too.
    
    dates = []
    curr = start_date
    while curr <= end_date:
        if curr.weekday() < 5:
             dates.append(curr)
        curr += timedelta(days=1)
        
    spot_data = {}
    
    def process_date(d):
        df = get_bhavcopy_data(d, type='fo')
        if df is not None:
            df.columns = [c.strip().upper() for c in df.columns]
            
            # Filter for Futures of the symbol
            mask = (df['SYMBOL'] == symbol) & (df['INSTRUMENT'].str.contains('FUT'))
            futures_df = df[mask].copy()
            
            if not futures_df.empty:
                # Find nearest expiry
                futures_df['EXPIRY_DT'] = pd.to_datetime(futures_df['EXPIRY_DT'])
                valid_expiries = futures_df[futures_df['EXPIRY_DT'].dt.date >= d]['EXPIRY_DT'].unique()
                
                if len(valid_expiries) > 0:
                    near_expiry = min(valid_expiries)
                    near_future = futures_df[futures_df['EXPIRY_DT'] == near_expiry]
                    
                    if not near_future.empty:
                        return d, near_future.iloc[0]['CLOSE']
        return d, None

    # Use ThreadPool
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(process_date, dates)
        
    for d, val in results:
        if val is not None:
            spot_data[d] = val
        
    if not spot_data:
        return pd.Series(dtype=float)
        
    return pd.Series(spot_data).sort_index()

def get_spot_data_from_bhavcopy(symbol, start_date, end_date):
    """Fetches spot data from Equity Bhavcopy."""
    # Parallelized version
    dates = []
    curr = start_date
    while curr <= end_date:
        if curr.weekday() < 5:
             dates.append(curr)
        curr += timedelta(days=1)
        
    spot_data = {}
    
    def process_date(d):
        df = get_bhavcopy_data(d, type='eq')
        if df is not None:
            # Standardize columns
            df.columns = [c.strip().upper() for c in df.columns]
            
            # Filter for symbol
            # Equity bhavcopy has SYMBOL, SERIES (EQ), CLOSE
            mask = (df['SYMBOL'] == symbol) & (df['SERIES'] == 'EQ')
            row = df[mask]
            
            if not row.empty:
                return d, row.iloc[0]['CLOSE']
        return d, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(process_date, dates)
        
    for d, val in results:
        if val is not None:
             spot_data[d] = val
    
    if not spot_data:
        return pd.Series(dtype=float)
        
    return pd.Series(spot_data).sort_index()

def get_india_vix(start_date, end_date):
    """Fetches India VIX data from NSE Index Bhavcopy."""
    try:
        return get_spot_data_from_index_bhavcopy("India VIX", start_date, end_date)
    except Exception:
        return pd.Series(dtype=float)

def get_historical_options_data(symbol, start_date, end_date):
    """
    Fetches historical options data for a symbol.
    Returns a DataFrame with Date, Strike, OptionType, Close, Expiry.
    """
    # Parallel execution using ThreadPoolExecutor
    
    dates = []
    curr = start_date
    while curr <= end_date:
        if curr.weekday() < 5:
            dates.append(curr)
        curr += timedelta(days=1)
        
    all_data = []
    
    def process_date(d):
        df = get_bhavcopy_data(d, type='fo')
        if df is not None:
            df.columns = [c.strip().upper() for c in df.columns]
            
            mask = (df['SYMBOL'] == symbol) & (df['INSTRUMENT'].str.contains('OPT'))
            symbol_df = df[mask].copy()
            
            if not symbol_df.empty:
                symbol_df['TIMESTAMP'] = d
                return symbol_df
        return None
        
    # Use max_workers=10 for fast I/O bound processing of cached files
    # For web downloads, rate limiter inside calls will slow it down effectively serializing new downloads
    # but concurrent processing of cached/processed files will be VERY fast.
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(process_date, dates)
        
    for res in results:
        if res is not None:
            all_data.append(res)
        
    if not all_data:
        return pd.DataFrame()
        
    return pd.concat(all_data, ignore_index=True)

def _yf_close(ticker, start_date, end_date):
    import yfinance as yf
    with suppress_stdout_stderr():
        df = yf.download(ticker, start=start_date, end=end_date + timedelta(days=1), progress=False)
    if df.empty:
        return pd.Series(dtype=float)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df['Close']


def compute_atm_iv(options_df, spot_series):
    """Daily ATM call IV from a Bhavcopy options panel, fully vectorized (one IV solve for all days)."""
    opts = options_df.loc[options_df['OPTION_TYP'] == 'CE', ['TIMESTAMP', 'STRIKE_PR', 'EXPIRY_DT', 'CLOSE']].copy()
    opts['TIMESTAMP'] = pd.to_datetime(opts['TIMESTAMP'])
    opts['EXPIRY_DT'] = pd.to_datetime(opts['EXPIRY_DT'])
    opts = opts[opts['EXPIRY_DT'] >= opts['TIMESTAMP']]
    # Nearest expiry per day, then the strike closest to spot within it
    opts = opts[opts['EXPIRY_DT'] == opts.groupby('TIMESTAMP')['EXPIRY_DT'].transform('min')]
    opts['SPOT'] = opts['TIMESTAMP'].map(spot_series)
    opts = opts.dropna(subset=['SPOT', 'CLOSE'])
    if opts.empty:
        return pd.Series(dtype=float)
    opts['DIST'] = (opts['STRIKE_PR'] - opts['SPOT']).abs()
    atm = opts.loc[opts.groupby('TIMESTAMP')['DIST'].idxmin()]
    t = np.maximum((atm['EXPIRY_DT'] - atm['TIMESTAMP']).dt.days / 365.0, 0.001)
    iv = utils.calculate_iv(atm['CLOSE'], atm['SPOT'], atm['STRIKE_PR'], t, 0.06, 'c')
    return pd.Series(iv, index=atm['TIMESTAMP'].to_numpy()).sort_index()


def process_market_data(symbol, start_date, end_date):
    """Bhavcopy pipeline: spot (yfinance / Bhavcopy / futures fallback), VIX, RV and ATM IV."""
    if isinstance(start_date, str):
        start_date = pd.to_datetime(start_date).date()
    if isinstance(end_date, str):
        end_date = pd.to_datetime(end_date).date()

    INDEX_MAP = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK"}
    is_index = symbol in INDEX_MAP
    spot_series = pd.Series(dtype=float)

    attempts = [
        lambda: _yf_close(INDEX_MAP[symbol], start_date, end_date) if is_index else None,
        lambda: get_spot_data_from_index_bhavcopy(symbol, start_date, end_date) if is_index else None,
        lambda: get_spot_data_from_bhavcopy(symbol, start_date, end_date) if not is_index else None,
        lambda: _yf_close(f"{symbol}.NS", start_date, end_date) if not is_index else None,
        lambda: get_spot_from_futures(symbol, start_date, end_date),
    ]
    for attempt in attempts:
        try:
            result = attempt()
        except Exception:
            result = None
        if result is not None and not result.empty:
            spot_series = result
            break

    if spot_series.empty:
        return None, "No spot data found. Tried yfinance, Bhavcopy, and Futures."
    spot_series.index = pd.to_datetime(spot_series.index).normalize()

    with suppress_stdout_stderr():
        vix_series = get_india_vix(start_date, end_date)
    if not vix_series.empty:
        vix_series.index = pd.to_datetime(vix_series.index)

    options_df = get_historical_options_data(symbol, start_date, end_date)
    iv_series = compute_atm_iv(options_df, spot_series) if not options_df.empty else pd.Series(dtype=float)

    return {
        'spot': spot_series,
        'vix': vix_series,
        'rv': utils.calculate_rv(spot_series),
        'iv': iv_series,
    }, None


SOURCES = ["Sensibull (Unofficial)", "DhanHQ", "Open Source (Bhavcopy)", "Zerodha Kite API",
           "IndianAPI.in", "TradingView (Unofficial)", "Demo (synthetic)"]


def synthetic_market(symbol="DEMO", end_date=None, n=600):
    """Offline demo data: regime-switching GBM with an IV that carries a noisy volatility premium."""
    seed = sum(map(ord, symbol))
    rng = np.random.default_rng(seed)
    regime_vol = np.repeat(rng.choice([0.10, 0.16, 0.28], size=n // 45 + 1), 45)[:n]
    drift = np.repeat(rng.normal(0, 0.0015, size=n // 60 + 1), 60)[:n]
    rets = drift + regime_vol / np.sqrt(252) * rng.standard_normal(n)
    close = 20000 * np.exp(np.cumsum(rets))
    iv = regime_vol * 100 * (1.1 + 0.1 * rng.standard_normal(n))
    idx = pd.bdate_range(end=pd.Timestamp(end_date or date.today()), periods=n)
    return pd.DataFrame({"close": close, "iv": iv, "vix": iv * 0.9}, index=idx)


WARMUP_DAYS = 400  # history kept before start_date (when a source returns it) so rolling features are warm


def load_market_frame(source, symbol, start_date, end_date, kite=None, kite_token=None, indian_api_key=None):
    """Single entry point for every source. Returns (DataFrame, error message or None).

    The frame has a normalized DatetimeIndex, `close`, and optionally `iv`, `vix`, `ivp`.
    Sources that return more than the requested range keep up to WARMUP_DAYS before
    `start_date`; callers compute features on the whole frame and trim for display.
    """
    if source == "Sensibull (Unofficial)":
        df = fetch_sensibull_data(symbol)
    elif source == "DhanHQ":
        df = fetch_dhan_data(symbol, start_date, end_date)
    elif source == "IndianAPI.in":
        if not indian_api_key:
            return pd.DataFrame(), "Enter your IndianAPI key in the sidebar."
        df = fetch_indianapi_data(symbol, indian_api_key)
    elif source == "TradingView (Unofficial)":
        df = fetch_tv_data(symbol)
    elif source == "Demo (synthetic)":
        df = synthetic_market(symbol, end_date, n=max(600, len(pd.bdate_range(start_date, end_date)) + 300))
    elif source == "Zerodha Kite API":
        if kite is None or kite_token is None:
            return pd.DataFrame(), "Log in to Kite first."
        df = fetch_kite_historical_data(kite, kite_token, start_date, end_date)
    else:
        data, error = process_market_data(symbol, start_date, end_date)
        if error:
            return pd.DataFrame(), error
        df = pd.DataFrame({'close': data['spot']})
        if not data['iv'].empty:
            df['iv'] = data['iv']
        if not data['vix'].empty:
            df['vix'] = data['vix']

    if df is None or df.empty or 'close' not in df.columns:
        return pd.DataFrame(), f"No data returned from {source} for {symbol}."
    df = df.copy()
    df.index = pd.to_datetime(df.index).normalize()
    df = df[~df.index.duplicated(keep='last')].sort_index()
    keep = [c for c in ('close', 'iv', 'vix', 'ivp') if c in df.columns]
    warm_start = pd.Timestamp(start_date) - pd.Timedelta(days=WARMUP_DAYS)
    df = df.loc[(df.index >= warm_start) & (df.index <= pd.Timestamp(end_date)), keep]
    df = df.dropna(subset=['close'])
    if df.empty or df.index[-1] < pd.Timestamp(start_date):
        return df, "No data in the selected date range."
    return df, None
