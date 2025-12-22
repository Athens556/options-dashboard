from abc import ABC, abstractmethod
from typing import List, Dict, Optional
# No longer importing Tokenizer here to avoid circular imports if any, 
# but passing tokens list is fine.

class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def should_enter(self, tokens: List[str]) -> bool:
        """Determines if strategy should be entered based on active tokens."""
        pass
        
    @abstractmethod
    def get_exit_conditions(self) -> Dict:
        """Returns parameters for exit (e.g., profit target days, stop loss)."""
        pass
        
    def __str__(self):
        return self.name

class IronCondor(BaseStrategy):
    def __init__(self):
        super().__init__("Iron Condor")
        
    def should_enter(self, tokens: List[str]) -> bool:
        """
        Enter if:
        - Range Bound
        - High Volatility (VOL_HIGH or VOL_EXTREME)
        - No earnings soon
        """
        is_range_bound = "RANGE_BOUND" in tokens
        is_high_vol = "VOL_HIGH" in tokens or "VOL_EXTREME" in tokens
        no_event = "EARNINGS_SOON" not in tokens
        
        return is_range_bound and is_high_vol and no_event
        
    def get_exit_conditions(self) -> Dict:
        return {
            "max_days": 30,
            "take_profit_percent": 50,
            "stop_loss_percent": 100,
            "max_loss_potential": 10000, # Estimated per lot
            "max_gain_potential": 5000
        }

class LongStraddle(BaseStrategy):
    def __init__(self):
        super().__init__("Long Straddle")
        
    def should_enter(self, tokens: List[str]) -> bool:
        """
        Enter if:
        - Low Volatility (VOL_LOW or VOL_MID)
        - Expecting trend (TRENDING_UP/DOWN) OR News Spike
        """
        is_cheap_vol = "VOL_LOW" in tokens or "VOL_MID" in tokens
        
        # Catalysts
        is_trending = "TRENDING_UP" in tokens or "TRENDING_DOWN" in tokens
        has_news = "Attention_SPIKE" in tokens
        
        return is_cheap_vol and (is_trending or has_news)
        
    def get_exit_conditions(self) -> Dict:
        return {
            "max_days": 10,
            "take_profit_percent": 30,
            "stop_loss_percent": 20,
            "max_loss_potential": 5000,
            "max_gain_potential": 15000
        }

class DebitSpread(BaseStrategy):
    def __init__(self, direction="BULL"):
        self.direction = direction
        super().__init__(f"{direction.title()} Debit Spread")
        
    def should_enter(self, tokens: List[str]) -> bool:
        """
        Enter if:
        - Directional view supported by trend
        """
        if self.direction == "BULL":
            is_right_trend = "TRENDING_UP" in tokens
        else:
            is_right_trend = "TRENDING_DOWN" in tokens
            
        return is_right_trend
        
    def get_exit_conditions(self) -> Dict:
        return {
            "max_days": 20,
            "take_profit_percent": 40,
            "stop_loss_percent": 50,
            "max_loss_potential": 5000,
            "max_gain_potential": 5000
        }

def get_all_strategies() -> List[BaseStrategy]:
    return [
        IronCondor(),
        LongStraddle(),
        DebitSpread("BULL"),
        DebitSpread("BEAR")
    ]
