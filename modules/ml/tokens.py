from typing import List
from modules.dashboard.market_state import MarketState
from modules.dashboard.guardrails import TrendStrength, IVBucket, VRPBucket

class Tokenizer:
    """
    Converts a deterministic MarketState into a list of Tokens.
    Now uses Normalized Buckets for strictly defined regimes.
    """
    
    @staticmethod
    def get_tokens(state: MarketState) -> List[str]:
        tokens = []
        
        # 1. Trend Tokens
        if state.trend_strength == TrendStrength.STRONG:
            if state.trend_score > 0:
                tokens.append("TRENDING_UP")
            else:
                tokens.append("TRENDING_DOWN")
        else:
            tokens.append("RANGE_BOUND")  # Covers WEAK and MODERATE for now, or split if needed
            
        # 2. Volatility Tokens (Use Bucket Name directly)
        # e.g. VOL_LOW, VOL_MID, VOL_HIGH, VOL_EXTREME
        tokens.append(f"VOL_{state.iv_bucket.name}")
        
        # 3. VRP Tokens
        if state.vrp_bucket == VRPBucket.POSITIVE:
             tokens.append("POSITIVE_VRP")
        elif state.vrp_bucket == VRPBucket.NEGATIVE:
             tokens.append("NEGATIVE_VRP")
            
        # 4. Event Tokens
        if state.earnings_proximity:
            tokens.append("EARNINGS_SOON")
        if state.event_window:
            tokens.append("MACRO_EVENT")
            
        # 5. External Tokens
        if state.sentiment_score > 0.5:
            tokens.append("SENTIMENT_BULLISH")
        elif state.sentiment_score < -0.5:
            tokens.append("SENTIMENT_BEARISH")
            
        if state.trends_velocity > 10:
             tokens.append("Attention_SPIKE")
             
        return tokens

    @staticmethod
    def explain_token(token: str) -> str:
        explanations = {
            "TRENDING_UP": "Short MA > Long MA by significant margin",
            "TRENDING_DOWN": "Short MA < Long MA by significant margin",
            "RANGE_BOUND": "Price is consolidating vs moving averages",
            "VOL_LOW": "IV is in bottom 20% percentile",
            "VOL_HIGH": "IV is in top 20% percentile",
            "POSITIVE_VRP": "Implied Volatility > Realized Volatility",
            "NEGATIVE_VRP": "Realized Volatility > Implied Volatility (Gamma risk)",
            "EARNINGS_SOON": "Earnings event within X days"
        }
        return explanations.get(token, "No description available")
