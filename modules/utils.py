import numpy as np
import pandas as pd
import py_vollib_vectorized
import warnings

def calculate_rv(spot_series, window=20):
    """
    Calculates annualized Realized Volatility (RV).
    
    Args:
        spot_series (pd.Series): Series of spot prices.
        window (int): Rolling window for volatility calculation.
        
    Returns:
        pd.Series: Annualized Realized Volatility.
    """
    log_returns = np.log(spot_series / spot_series.shift(1))
    # Annualize by multiplying by sqrt(252)
    rv = log_returns.rolling(window=window).std() * np.sqrt(252) * 100
    return rv

def calculate_iv(price, S, K, t, r, flag):
    """
    Calculates Implied Volatility (IV) using py_vollib_vectorized.
    
    Args:
        price (float/pd.Series): Option price.
        S (float/pd.Series): Underlying spot price.
        K (float/pd.Series): Strike price.
        t (float/pd.Series): Time to expiration in years.
        r (float/pd.Series): Risk-free interest rate.
        flag (str/pd.Series): 'c' for Call, 'p' for Put.
        
    Returns:
        pd.Series: Implied Volatility.
    """
    # py_vollib_vectorized handles vectorization automatically
    # Suppress "Found Below Intrinsic contracts" warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return py_vollib_vectorized.vectorized_implied_volatility(price, S, K, t, r, flag, return_as='numpy') * 100

def get_atm_strike(spot_price, step=50):
    """
    Finds the nearest ATM strike price.
    
    Args:
        spot_price (float): Current spot price.
        step (int): Strike price step (default 50 for NIFTY, varies for stocks).
        
    Returns:
        int: Nearest strike price.
    """
    return round(spot_price / step) * step

def get_instrument_token(kite, symbol, exchange="NSE"):
    """
    Fetches instrument token for a given symbol from Kite.
    
    Args:
        kite (KiteConnect): Authenticated KiteConnect instance.
        symbol (str): Trading symbol (e.g., 'SBIN', 'NIFTY 50').
        exchange (str): Exchange (default 'NSE').
        
    Returns:
        int: Instrument token or None if not found.
    """
    try:
        instruments = kite.instruments(exchange)
        for instrument in instruments:
            if instrument['tradingsymbol'] == symbol:
                return instrument['instrument_token']
    except Exception as e:
        print(f"Error fetching instrument token: {e}")
    return None

def calculate_iv_percentile(iv_series, period=252):
    """
    Calculates IV Percentile (IVP) over a rolling window.
    IVP = (Count of days where Historic IV < Current IV) / Total Days
    """
    return iv_series.rolling(window=period, min_periods=period//2).apply(
        lambda x: (x < x.iloc[-1]).sum() / len(x) * 100, raw=False
    )
