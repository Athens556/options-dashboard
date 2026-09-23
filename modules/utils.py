"""Vectorized numeric helpers. Pure numpy/pandas — no heavy imports at load time."""
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from scipy.special import ndtr

TRADING_DAYS = 252
RISK_FREE = 0.065  # India ~6.5%


def calculate_rv(spot_series, window=20):
    """Annualized realized volatility (%) from close prices."""
    log_returns = np.log(spot_series.astype(float)).diff()
    return log_returns.rolling(window=window).std() * np.sqrt(TRADING_DAYS) * 100


def rolling_percentile(series: pd.Series, window=252, min_periods=60) -> pd.Series:
    """% of the trailing window strictly below the current value. Causal and fully vectorized."""
    x = series.to_numpy(dtype=float)
    out = np.full(len(x), np.nan)
    if len(x) == 0:
        return pd.Series(out, index=series.index)
    padded = np.concatenate([np.full(window - 1, np.nan), x])
    win = sliding_window_view(padded, window)  # (n, window), last column == x
    counts = (~np.isnan(win)).sum(axis=1)
    below = (win < x[:, None]).sum(axis=1)  # NaN compares False
    with np.errstate(invalid="ignore", divide="ignore"):
        out = below / counts * 100
    out[(counts < min_periods) | np.isnan(x)] = np.nan
    return pd.Series(out, index=series.index)


def calculate_iv_percentile(iv_series, period=252):
    return rolling_percentile(iv_series, window=period, min_periods=period // 2)


def bs_price(flag, S, K, T, sigma, r=RISK_FREE):
    """Black-Scholes price, vectorized. flag: 'c'/'p' (scalar or array)."""
    S, K, T, sigma = (np.asarray(a, dtype=float) for a in (S, K, T, sigma))
    sqrt_t = np.sqrt(np.maximum(T, 1e-9))
    vol = np.maximum(sigma, 1e-9) * sqrt_t
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / vol
    d2 = d1 - vol
    disc = K * np.exp(-r * T)
    call = S * ndtr(d1) - disc * ndtr(d2)
    put = disc * ndtr(-d2) - S * ndtr(-d1)
    is_call = np.char.lower(np.asarray(flag).astype(str)) == "c"
    return np.where(is_call, call, put)


def calculate_iv(price, S, K, t, r, flag, iters=64):
    """Implied volatility (%) by vectorized bisection. NaN where price is outside no-arb bounds."""
    price, S, K, t = np.broadcast_arrays(*(np.asarray(a, dtype=float) for a in (price, S, K, t)))
    flag = np.broadcast_to(np.asarray(flag), price.shape)
    lo = np.full(price.shape, 1e-4)
    hi = np.full(price.shape, 5.0)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        too_high = bs_price(flag, S, K, t, mid, r) > price
        hi = np.where(too_high, mid, hi)
        lo = np.where(too_high, lo, mid)
    iv = 0.5 * (lo + hi)
    lower = bs_price(flag, S, K, t, 1e-4, r)
    upper = bs_price(flag, S, K, t, 5.0, r)
    iv = np.where((price <= lower) | (price >= upper), np.nan, iv)
    return iv * 100


def get_atm_strike(spot_price, step=50):
    return round(spot_price / step) * step


def get_instrument_token(kite, symbol, exchange="NSE", instruments=None):
    """Instrument token lookup. Pass a pre-fetched `instruments` list to avoid a re-download."""
    try:
        instruments = instruments if instruments is not None else kite.instruments(exchange)
        for instrument in instruments:
            if instrument["tradingsymbol"] == symbol:
                return instrument["instrument_token"]
    except Exception as e:
        print(f"Error fetching instrument token: {e}")
    return None
