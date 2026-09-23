"""Market state features, computed for every day in one vectorized pass.

Every column uses only data up to and including its own row (rolling windows,
shifts into the past). `causality_audit` proves it by recomputing on truncated
history and checking the rows match.
"""
import numpy as np
import pandas as pd

from modules.utils import TRADING_DAYS, calculate_rv, rolling_percentile

SHORT_MA, LONG_MA = 20, 50


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    if name in df.columns and df[name].notna().any():
        return df[name].astype(float)
    return pd.Series(np.nan, index=df.index)


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """df: DatetimeIndex with `close` and optional `iv`, `vix`, `ivp` columns."""
    close = df["close"].astype(float)
    out = pd.DataFrame(index=df.index)
    out["close"] = close
    out["ret1"] = close.pct_change() * 100
    out["ma20"] = close.rolling(SHORT_MA).mean()
    out["ma50"] = close.rolling(LONG_MA).mean()
    out["rv10"] = calculate_rv(close, 10)
    out["rv20"] = calculate_rv(close, 20)
    out["rv30"] = calculate_rv(close, 30)

    # Trend & momentum are volatility-normalized so NIFTY and a high-beta stock share one scale.
    sigma20 = out["rv20"] / 100 * np.sqrt(SHORT_MA / TRADING_DAYS)
    sigma5 = out["rv20"] / 100 * np.sqrt(5 / TRADING_DAYS)
    out["trend_z"] = (out["ma20"] / out["ma50"] - 1) / sigma20
    out["mom_z"] = np.log(close / close.shift(5)) / sigma5

    # Days without options data fall back to realized vol so the gym can still run; flagged per row.
    raw_iv = _col(df, "iv")
    out["iv_is_proxy"] = raw_iv.isna() & out["rv20"].notna()
    iv = raw_iv.fillna(out["rv20"])
    out["iv"] = iv
    ivp = _col(df, "ivp")
    out["iv_pct"] = ivp if ivp.notna().any() else rolling_percentile(iv)
    out["iv_chg5"] = (iv / iv.shift(5) - 1) * 100
    out["vrp"] = iv - out["rv20"]
    out["vrp_ratio"] = iv / out["rv20"]
    out["rv_ratio"] = out["rv10"] / out["rv30"]

    vix = _col(df, "vix")
    out["vix"] = vix
    out["vix_pct"] = rolling_percentile(vix)
    return out


def causality_audit(df: pd.DataFrame, n_checks=5, seed=0) -> bool:
    """Recompute features on history truncated at random dates; the truncation-day row must not change."""
    full = build_feature_frame(df)
    if len(df) < 80:
        return True
    rng = np.random.default_rng(seed)
    cut_points = rng.choice(np.arange(60, len(df) - 1), size=min(n_checks, len(df) - 61), replace=False)
    for cut in cut_points:
        partial = build_feature_frame(df.iloc[: cut + 1]).iloc[-1]
        if not np.allclose(partial.to_numpy(float), full.iloc[cut].to_numpy(float), equal_nan=True):
            return False
    return True
