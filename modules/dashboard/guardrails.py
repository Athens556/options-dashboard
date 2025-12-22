import pandas as pd
from datetime import date, datetime
from typing import Union, Tuple
from enum import Enum

class TimeGuard:
    """
    Enforces strict temporal causality.
    Guarantess that no data from future (> current_date) is accessed.
    """
    def __init__(self, current_date: Union[date, datetime]):
        # normalize to date
        if isinstance(current_date, datetime):
            self.current_date = current_date.date()
        else:
            self.current_date = current_date
            
    def slice(self, series: pd.Series) -> pd.Series:
        """
        Returns a view of the series strictly up to current_date.
        """
        if series.empty:
            return series
            
        # Determine strict cutoff
        # If series index is DatetimeIndex, we treat current_date as inclusive (End of Day)
        if isinstance(series.index, pd.DatetimeIndex):
            # Create a Timestamp for the END of the current_date to include intraday data
            cutoff = pd.Timestamp(self.current_date) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            return series[series.index <= cutoff]
            
        # If index consists of date objects (object dtype)
        # We assume they are comparable to datetime.date
        # Note: This relies on user ensuring index consistency.
        return series[series.index <= self.current_date]
        
    def peek_check(self, series: pd.Series):
        """
        Raises error if the Series specifically contains any future data.
        Useful for auditing passed datasets.
        """
        max_date = series.index.max()
        if isinstance(max_date, pd.Timestamp):
            max_date = max_date.date()
            
        if max_date > self.current_date:
            raise ValueError(f"Future Leakage Detected! Data max {max_date} > Current {self.current_date}")

class TrendStrength(Enum):
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"

class IVBucket(Enum):
    LOW = "LOW"       # < 20 percentile
    MID = "MID"       # 20 - 50
    HIGH = "HIGH"     # 50 - 80
    EXTREME = "EXTREME" # > 80

class VRPBucket(Enum):
    NEGATIVE = "NEGATIVE" # RV > IV
    NEUTRAL = "NEUTRAL"   # IV ~ RV
    POSITIVE = "POSITIVE" # IV > RV significantly

class Bucketer:
    """
    Normalizes continuous values into discrete regimes.
    """
    
    @staticmethod
    def bucket_iv(percentile: float) -> IVBucket:
        if percentile < 20: return IVBucket.LOW
        if percentile < 50: return IVBucket.MID
        if percentile < 80: return IVBucket.HIGH
        return IVBucket.EXTREME

    @staticmethod
    def bucket_vrp(iv: float, rv: float) -> VRPBucket:
        spread = iv - rv
        # Thresholds can be adjusted
        if spread < -2.0: return VRPBucket.NEGATIVE
        if spread < 2.0: return VRPBucket.NEUTRAL
        return VRPBucket.POSITIVE
        
    @staticmethod
    def bucket_trend(trend_score: float) -> TrendStrength:
        abs_score = abs(trend_score)
        if abs_score < 0.02: return TrendStrength.WEAK      # < 2% divergence
        if abs_score < 0.05: return TrendStrength.MODERATE  # 2-5% divergence
        return TrendStrength.STRONG                         # > 5% divergence
