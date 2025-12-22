from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from datetime import date
from .market_state import MarketState

@dataclass
class TradeLog:
    """
    Comprehensive log for a single trade decision.
    Answer: "Why did we trade this?"
    """
    date: date
    symbol: str
    strategy_name: str
    action: str # "ENTRY" or "NO_TRADE"
    
    # Context
    tokens: List[str]
    state_snapshot: Dict[str, Any]
    
    # Decision Reasoning
    reasoning: str
    belief_at_entry: Dict[str, float] # alpha, beta, score
    
    # Outcome (filled later)
    pnl: float = 0.0
    win: bool = False
    
    def to_dict(self):
        return asdict(self)
