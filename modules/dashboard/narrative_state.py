from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
import pandas as pd
from datetime import datetime
from modules.api import news_loader
from .db_manager import DBManager

class NarrativeStatus(Enum):
    PRESENT = "NARRATIVE_PRESENT"
    ABSENT = "NARRATIVE_ABSENT"
    UNCERTAIN = "NARRATIVE_UNCERTAIN"

@dataclass
class NarrativeState:
    status: NarrativeStatus
    description: str
    drivers: List[str] # ["Earnings", "High News Volume", "Trend Spike"]
    
    def get_tokens(self) -> List[str]:
        return [self.status.value]

class NarrativeStateBuilder:
    def __init__(self):
        self.db = DBManager()
        
    def build_state(self, symbol: str, current_date: datetime) -> NarrativeState:
        drivers = []
        is_uncertain = False
        
        # 1. Earnings Check (Deterministic)
        # Placeholder: In a real system, would check an Earnings Calendar DB.
        # For now, let's assume no earnings unless manually flagged or provided in market_state.
        earnings_proximity = False # TODO: Integrate with MarketState.earnings_proximity
        
        if earnings_proximity:
            drivers.append("Earnings Nearby")
            
        # 2. Google Trends (Cache First)
        # Google Trends Disabled by User Request
        # try:
        #     # We use fetch_google_trends which now handles caching
        #     trends_df = news_loader.fetch_google_trends(symbol)
        #     if not trends_df.empty:
        #         # Check for spike in last 5 days relative to 30dMA
        #         # Need historical data. fetch_google_trends returns 1 year.
        #         # Find current_date index
        #         # Ensure index is datetime
        #         trends_df.index = pd.to_datetime(trends_df.index)
        #         
        #         # Filter up to current_date
        #         # If current_date is not in index (e.g. today), take latest
        #         if current_date in trends_df.index:
        #             latest_val = trends_df.loc[current_date][symbol]
        #         else:
        #             latest_val = trends_df.iloc[-1][symbol]
        #             
        #         # Simple Z-Score approx
        #         history = trends_df[symbol].tail(30)
        #         mean = history.mean()
        #         std = history.std()
        #         
        #         if std > 0 and (latest_val - mean) / std > 2.0:
        #             drivers.append("Viral Trend Spike")
        #     else:
        #         # If dataframe is empty, it means we couldn't fetch data.
        #         is_uncertain = True
        #         
        # except Exception as e:
        #     print(f"Narrative Builder Trends Error: {e}")
        #     is_uncertain = True
            
        # 3. News Volume (Optional)
        # news = news_loader.fetch_google_news(symbol) ...
        
        # Determine Status
        if is_uncertain:
            return NarrativeState(NarrativeStatus.UNCERTAIN, "Data unavailable", [])
            
        if drivers:
            return NarrativeState(NarrativeStatus.PRESENT, "Narrative Active", drivers)
            
        return NarrativeState(NarrativeStatus.ABSENT, "No significant narrative", [])
