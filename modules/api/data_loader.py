import pandas as pd
import yfinance as yf
from jugaad_data.nse import bhavcopy_fo_save, bhavcopy_save
from datetime import date, timedelta, datetime
import os
from modules import utils
import numpy as np
import sys
import contextlib
from kiteconnect import KiteConnect
from dhanhq import dhanhq
from . import dhan_config


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
        response = requests.get(url, headers=headers)
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
    kite = KiteConnect(api_key=api_key)
    return kite.login_url()

def generate_kite_session(api_key, api_secret, request_token):
    """Generates a Kite session and returns the authenticated instance."""
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
            # Kite returns timezone aware datetimes, ensure compatibility
            df.index = df.index.date
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
        response = requests.get(base_url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if 'datasets' in data and len(data['datasets']) > 0:
                values = data['datasets'][0]['values']
                # values is list of [date, price]
                df = pd.DataFrame(values, columns=['date', 'close'])
                df['date'] = pd.to_datetime(df['date']).dt.date
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
            df.index = df.index.date
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
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            if 'payload' in data and 'chart_data' in data['payload']:
                chart_data = data['payload']['chart_data']
                
                records = []
                for timestamp, values in chart_data.items():
                    record = {'date': timestamp}
                    
                    # Spot
                    if 'spot' in values:
                        record['close'] = values['spot']
                        
                    # IV
                    if 'iv' in values and 'atm_iv' in values['iv']:
                        record['iv'] = values['iv']['atm_iv']
                        
                    # India VIX
                    if 'indiavix' in values and 'indiavix_price' in values['indiavix']:
                        record['vix'] = values['indiavix']['indiavix_price']
                        
                    # IV Percentile
                    if 'ivp' in values and 'ivp' in values['ivp']:
                        record['ivp'] = values['ivp']['ivp']
                        
                    records.append(record)
                    
                df = pd.DataFrame(records)
                if not df.empty:
                    df['date'] = pd.to_datetime(df['date']).dt.date
                    df.set_index('date', inplace=True)
                    df.sort_index(inplace=True)
                    return df
    except Exception as e:
        print(f"Error fetching Sensibull data: {e}")
        
    return pd.DataFrame()

def get_dhan_client():
    """Returns authenticated Dhan client."""
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
                         df['date'] = pd.to_datetime(df['date'], unit='s' if df['date'].iloc[0] > 1e9 else 'ns').dt.date
                     else:
                         df['date'] = pd.to_datetime(df['date']).dt.date
                     
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
            # Identify Indices
            # Known indices in FO
            indices = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]
            
            def get_instrument(row):
                symbol = row.get('SYMBOL')
                opt_type = row.get('OPTION_TYP')
                
                is_index = symbol in indices
                is_opt = isinstance(opt_type, str) and opt_type in ['CE', 'PE']
                
                if is_index:
                    return 'OPTIDX' if is_opt else 'FUTIDX'
                else:
                    return 'OPTSTK' if is_opt else 'FUTSTK'
                    
            df['INSTRUMENT'] = df.apply(get_instrument, axis=1)
            
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
                        file_path = bhavcopy_fo_save(date_obj, DATA_DIR)
        elif type == 'eq':
            fname = f"cm{date_obj.strftime('%d%b%Y').upper()}bhav.csv"
            with lock_manager.get_lock(fname):
                file_path = os.path.join(DATA_DIR, fname)
                if not os.path.exists(file_path):
                    file_path = bhavcopy_save(date_obj, DATA_DIR)
        else:
            return None
            
        df = pd.read_csv(file_path)
        return df
    except Exception as e:
        # print(f"Failed to fetch {type} data for {date_obj}: {e}")
        return None

def get_spot_data_from_index_bhavcopy(symbol, start_date, end_date):
    """Fetches spot data from Index Bhavcopy."""
    from jugaad_data.nse import bhavcopy_index_save
    spot_data = {}
    current_date = start_date
    
    # This also needs simple iteration or we could parallelize, 
    # but let's stick to parallelizing the main bottleneck (options data).
    while current_date <= end_date:
        if current_date.weekday() < 5:
            try:
                # Correct filename format: ind_close_all_DDMMYYYY.csv
                fname = f"ind_close_all_{current_date.strftime('%d%m%Y')}.csv"
                with lock_manager.get_lock(fname):
                    file_path = os.path.join(DATA_DIR, fname)
                    if not os.path.exists(file_path):
                        # Timeout handling could be added here if needed, but jugaad-data might retry internally
                        bhavcopy_index_save(current_date, DATA_DIR)
                
                if os.path.exists(file_path):
                    df = pd.read_csv(file_path)
                    df.columns = [c.strip().upper() for c in df.columns]
                    # Index bhavcopy: 'Index Name', 'Closing Index Value', ...
                    # Symbol for NIFTY 50 is usually 'Nifty 50'
                    
                    # Map common symbols to Index Names in Bhavcopy
                    name_map = {
                        "NIFTY": "Nifty 50",
                        "BANKNIFTY": "Nifty Bank"
                    }
                    search_name = name_map.get(symbol, symbol)
                    
                    mask = (df['INDEX NAME'] == search_name)
                    row = df[mask]
                    
                    if not row.empty:
                        spot_data[current_date] = row.iloc[0]['CLOSING INDEX VALUE']
            except Exception:
                pass
        
        current_date += timedelta(days=1)
    
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

def process_market_data(symbol, start_date, end_date):
    """
    Orchestrates data fetching and processing.
    """
    # Convert string dates to date objects if needed
    if isinstance(start_date, str):
        start_date = pd.to_datetime(start_date).date()
    if isinstance(end_date, str):
        end_date = pd.to_datetime(end_date).date()

    # 1. Get Spot Data
    # Handle Indices specifically
    INDEX_MAP = {
        "NIFTY": "^NSEI",
        "BANKNIFTY": "^NSEBANK"
    }
    
    spot_series = pd.Series(dtype=float)
    
    # Strategy 1: Try yfinance for Indices
    if symbol in INDEX_MAP:
        try:
            ticker = INDEX_MAP[symbol]
            with suppress_stdout_stderr():
                df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if not df.empty:
                 if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                 spot_series = df['Close']
        except Exception:
            pass
            
    # Strategy 2: Try Index Bhavcopy (if Strategy 1 failed or not an index)
    if spot_series.empty and symbol in INDEX_MAP:
        spot_series = get_spot_data_from_index_bhavcopy(symbol, start_date, end_date)

    # Strategy 3: Try Equity Bhavcopy (for stocks)
    if spot_series.empty and symbol not in INDEX_MAP:
        spot_series = get_spot_data_from_bhavcopy(symbol, start_date, end_date)
    
    # Strategy 4: Fallback to yfinance for stocks
    if spot_series.empty and symbol not in INDEX_MAP:
        try:
            ticker = f"{symbol}.NS"
            with suppress_stdout_stderr():
                df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if not df.empty:
                 if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                 spot_series = df['Close']
        except:
            pass

    # Strategy 5: Fallback to Futures Price (Last Resort for Indices/Stocks)
    if spot_series.empty:
        # print(f"Falling back to Futures price for {symbol}")
        spot_series = get_spot_from_futures(symbol, start_date, end_date)

    if spot_series.empty:
        return None, "No spot data found. Tried yfinance, Bhavcopy, and Futures."
        
    # 2. Get India VIX
    with suppress_stdout_stderr():
        vix_series = get_india_vix(start_date, end_date)
    
    # 3. Calculate RV
    rv_series = utils.calculate_rv(spot_series)
    
    # 4. Get Options Data
    options_df = get_historical_options_data(symbol, start_date, end_date)
    
    iv_series = pd.Series(dtype=float)
    
    if not options_df.empty:
        # Pre-processing for IV calculation
        options_df['EXPIRY_DT'] = pd.to_datetime(options_df['EXPIRY_DT'])
        
        daily_ivs = {}
        
        # Iterate over spot series dates to ensure alignment
        for date_val in spot_series.index:
            # Handle both datetime and date objects in index
            date_date = date_val.date() if hasattr(date_val, 'date') else date_val
            
            if date_date not in options_df['TIMESTAMP'].values:
                continue
                
            spot_price = spot_series.loc[date_val]
            if pd.isna(spot_price):
                continue

            # Find ATM Strike
            day_opts = options_df[options_df['TIMESTAMP'] == date_date]
            if day_opts.empty:
                continue
                
            available_strikes = day_opts['STRIKE_PR'].unique()
            if len(available_strikes) == 0:
                continue
                
            atm_strike = min(available_strikes, key=lambda x: abs(x - spot_price))
            
            # Get nearest expiry (monthly)
            valid_expiries = day_opts[day_opts['EXPIRY_DT'].dt.date >= date_date]['EXPIRY_DT'].unique()
            if len(valid_expiries) == 0:
                continue
            near_expiry = min(valid_expiries)
            
            # Get Option Price for ATM Strike and Near Expiry
            opt_row = day_opts[
                (day_opts['STRIKE_PR'] == atm_strike) & 
                (day_opts['EXPIRY_DT'] == near_expiry) & 
                (day_opts['OPTION_TYP'] == 'CE')
            ]
            
            if opt_row.empty:
                continue
                
            price = opt_row.iloc[0]['CLOSE']
            
            # Calculate Time to Expiry in years
            days_to_expiry = (near_expiry.date() - date_date).days
            t = max(days_to_expiry / 365.0, 0.001)
            
            # Risk free rate - assume 6%
            r = 0.06
            
            try:
                iv = utils.calculate_iv(price, spot_price, atm_strike, t, r, 'c')
                # py_vollib_vectorized returns numpy array, extract float
                if isinstance(iv, np.ndarray):
                    iv = iv[0]
                daily_ivs[date_val] = iv
            except Exception:
                continue
            
        iv_series = pd.Series(daily_ivs)
    
    return {
        'spot': spot_series,
        'vix': vix_series,
        'rv': rv_series,
        'iv': iv_series
    }, None
