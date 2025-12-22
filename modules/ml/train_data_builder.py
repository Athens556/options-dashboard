import pandas as pd
from datetime import timedelta
import sqlite3
from typing import List, Tuple, Dict
from modules.dashboard.db_manager import DBManager
from .token_signature import TokenSignature

class TrainingDatasetBuilder:
    """
    Extracts historical contexts and labels them for 'Belief Alignment'.
    Target: 1 if the token context led to a winning trade, 0 otherwise.
    Or more specifically: Which tokens in the set were 'Active' in a winning strategy?
    
    Simplified Training Objective for Phase 4:
    Input: [CLS, Token1, Token2, ...]
    Target: Binary Label for the whole set? OR Masked Language Model?
    
    User Constraint: 'Target: which tokens were present in successful belief updates'
    
    Approach:
    1. Fetch all trades from DB (strategy_performance or reconstruct from beliefs).
    2. Filter for WIN trades.
    3. Get the 'tokens' active at that trade entry.
    4. These tokens are POSITIVE examples.
    5. Tokens present in LOSS trades are NEGATIVE examples (softly).
    
    Dataset Format:
    List of (TokenSet, Label_Vector)?
    Actually, we want to learn Attention.
    If we have a set {A, B, C} and it Won, we want Attn(A), Attn(B), Attn(C) to be high? Not necessarily.
    Maybe {A} was the signal and {B, C} were noise.
    
    Refined Objective (Weak Supervision):
    If Strategy "IronCondor" Won, and it relies on "VOL_HIGH" + "RANGE_BOUND".
    Then "VOL_HIGH" and "RANGE_BOUND" get a positive label for that day.
    "EARNINGS_SOON" (if present but ignored by strategy) gets 0 label?
    
    Let's implement 'extract_training_examples':
    Returns: List of (Tokens, TargetMask)
    TargetMask: 1.0 for tokens that matched the Winning Strategy's conditions.
    """
    
    def __init__(self, db: DBManager):
        self.db = db
        
    def extract_examples(self) -> List[Tuple[List[str], Dict[str, float]]]:
        """
        Returns pairs of (InputTokens, TargetAttentionMap).
        TargetAttentionMap = {Token: 1.0 if relevant else 0.0}
        """
        # We need historical trades. Backtest logs are best.
        # But DB currently stores 'strategy_beliefs' (aggregated) and 'market_states'.
        # 'strategy_performance' table was defined in Init but is it populated?
        # The BacktestEngine keeps results in memory mostly, but let's check if we persist them.
        # BacktestEngine calls db.update_belief, but does it insert into strategy_performance?
        # Checking db_manager... NO. It only updates beliefs.
        
        # So we relying on 'strategy_beliefs' is hard because it's aggregated.
        # We need per-trade outcomes.
        
        # ACTION: We need to run a Backtest to generate the Dataset!
        # This is actually better: "Replay historical data".
        
        return []

    def build_from_backtest_results(self, trades: List[Dict]) -> List[Tuple[List[str], Dict[str, float]]]:
        examples = []
        
        for trade in trades:
            tokens = trade['tokens']
            win = trade['result']['win']
            strategy_name = trade['strategy']
            
            # Simple Heuristic Labeling:
            # If Win: The tokens that caused entry are "Salient".
            # We need to know WHICH tokens caused entry.
            # BaseStrategy.should_enter return boolean, but doesn't say "because of X".
            # But we know the logic encoded in Strategy classes.
            # We can infer it by checking the strategy logic again or hardcoding dependencies.
            
            # For Phase 4, let's use a simpler proxy:
            # If Win: All tokens present are treated as "Potentially Relevant" (Label 1.0).
            # If Loss: All tokens present are "Distractors" (Label 0.0).
            # The Model will average this out. If 'VOL_HIGH' appears in 10 wins and 2 losses, it learns high weight.
            # If 'RANDOM_NOISE' appears in 5 wins and 5 losses, it learns low weight (0.5).
            
            target_label = 1.0 if win else 0.0
            
            # Create a target map
            target_map = {t: target_label for t in tokens}
            
            examples.append((tokens, target_map))
            
        return examples
