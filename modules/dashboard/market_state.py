from dataclasses import dataclass, asdict
from datetime import date
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np

# Guardrails
from .guardrails import TimeGuard, Bucketer, TrendStrength, IVBucket, VRPBucket

@dataclass
class MarketState:
    """
    Represents a snapshot of the market at a specific date.
    Strictly causal: All features must be known at the end of 'date'.
    Normalized: Uses Buckets/Enums for key regimes.
    """
    symbol: str
    date: date
    spot_price: float
    
    # Technicals
    trend_score: float
    trend_strength: TrendStrength
    is_trending: bool 
    regime_label: str 
    
    # Volatility
    iv: float
    rv: float
    vrp: float
    iv_percentile: float
    iv_bucket: IVBucket
    vrp_bucket: VRPBucket
    volatility_regime: str 
    
    # Sentiment / External
    sentiment_score: float = 0.0
    trends_velocity: float = 0.0
    earnings_proximity: bool = False
    event_window: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Convert Enums to string for serialization
        data['trend_strength'] = self.trend_strength.name
        data['iv_bucket'] = self.iv_bucket.name
        data['vrp_bucket'] = self.vrp_bucket.name
        return data

class MarketStateBuilder:
    def __init__(self):
        pass
        
    def build_daily_state(self, symbol: str, current_date: date, 
                         spot_series: pd.Series, 
                         iv_series: pd.Series, 
                         rv_series: pd.Series,
                         news_sentiment: float = 0.0,
                         trends_vel: float = 0.0) -> Optional[MarketState]:
        
        # 1. TIMEGUARD: Enforce Strict Causality
        # We assume the input series contains ALL history available.
        # We must slice it strictly <= current_date.
        tg = TimeGuard(current_date)
        try:
            spot_hist = tg.slice(spot_series)
            iv_hist = tg.slice(iv_series)
            rv_hist = tg.slice(rv_series)
        except Exception as e:
            print(f"TimeGuard Error: {e}")
            return None

        # Check if we have data for the exact target date
        ts_date = pd.Timestamp(current_date)
        
        # Check membership (Relaxed for date vs Timestamp)
        has_date = (current_date in spot_hist.index) or (ts_date in spot_hist.index)
        
        if spot_hist.empty or not has_date:
            return None
            
        # 2. Calculate Features using History
        tech_feats = self.calculate_technical_features(spot_hist)
        vol_feats = self.calculate_volatility_features(iv_hist, rv_hist, current_date)
        
        if not tech_feats or not vol_feats:
            return None
            
        return MarketState(
            symbol=symbol,
            date=current_date,
            spot_price=spot_hist.iloc[-1],
            
            # Trend
            trend_score=tech_feats['trend_score'],
            trend_strength=tech_feats['trend_strength'],
            is_trending=tech_feats['is_trending'],
            regime_label=tech_feats['regime_label'],
            
            # Volatility
            iv=vol_feats['iv'],
            rv=vol_feats['rv'],
            vrp=vol_feats['vrp'],
            iv_percentile=vol_feats['iv_percentile'],
            iv_bucket=vol_feats['iv_bucket'],
            vrp_bucket=vol_feats['vrp_bucket'],
            volatility_regime=vol_feats['volatility_regime'],
            
            # External
            sentiment_score=news_sentiment,
            trends_velocity=trends_vel
        )

    def calculate_technical_features(self, spot_hist: pd.Series, short_window=20, long_window=50) -> Dict:
        if len(spot_hist) < long_window:
            return {}
            
        # Calculate Rolling MAs (using sliced history, so .iloc[-1] IS current_date)
        short_ma = spot_hist.rolling(window=short_window).mean().iloc[-1]
        long_ma = spot_hist.rolling(window=long_window).mean().iloc[-1]
        
        if long_ma == 0: return {} # Avoid div by zero
        
        trend_score = (short_ma - long_ma) / long_ma
        
        # BUCKETER
        strength = Bucketer.bucket_trend(trend_score)
        
        # Backward compatibility
        is_trending = strength != TrendStrength.WEAK
        regime_label = "TRENDING" if is_trending else "RANGE_BOUND"
        
        return {
            "trend_score": trend_score,
            "trend_strength": strength,
            "is_trending": is_trending,
            "regime_label": regime_label
        }

    def calculate_volatility_features(self, iv_hist: pd.Series, rv_hist: pd.Series, current_date) -> Dict:
        if iv_hist.empty:
            return {}
            
        # Latest values
        iv = iv_hist.iloc[-1]
        rv = rv_hist.iloc[-1] if not rv_hist.empty else 0.0
        vrp = iv - rv
        
        # Calculate IV Percentile (Rank of current IV in last 252 days of HISTORY)
        history_window = iv_hist.tail(252)
        if len(history_window) > 0:
            iv_percentile = (history_window < iv).mean() * 100
        else:
            iv_percentile = 50.0
            
        # BUCKETER
        iv_bucket = Bucketer.bucket_iv(iv_percentile)
        vrp_bucket = Bucketer.bucket_vrp(iv, rv)
        
        # Backward compatibility
        regime = iv_bucket.name # LOW, MID, HIGH, EXTREME
        
        return {
            "iv": iv, "rv": rv, "vrp": vrp,
            "iv_percentile": iv_percentile,
            "iv_bucket": iv_bucket,
            "vrp_bucket": vrp_bucket,
            "volatility_regime": regime
        }
