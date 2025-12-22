import pandas as pd
from datetime import timedelta, date
from typing import List, Dict, Any
from .market_state import MarketStateBuilder, MarketState
from modules.ml.tokens import Tokenizer
from .db_manager import DBManager
from .strategy import BaseStrategy
from . import strategy as strategies
from modules.ml.token_signature import TokenSignature

class BacktestEngine:
    def __init__(self, symbol, start_date, end_date):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.db = DBManager()
        self.builder = MarketStateBuilder()
        
    def load_data(self):
        # Fetch from Sensibull as requested
        from modules.api import data_loader
        from modules import utils
        print("Fetching data (Sensibull) for backtest...")
        df = data_loader.fetch_sensibull_data(self.symbol)
        
        if df.empty:
            return None
            
        # Prepare Dictionary format expected by engine
        # Calculate RV
        rv_series = utils.calculate_rv(df['close'])
        
        return {
            'spot': df['close'],
            'iv': df['iv'] if 'iv' in df.columns else pd.Series(),
            'rv': rv_series,
            'vix': df['vix'] if 'vix' in df.columns else pd.Series()
        }

    def run(self, strategies_to_test: List[BaseStrategy]) -> Dict[str, List]:
        data = self.load_data()
        if not data:
            print("No data for backtest.")
            return {"trades": [], "history": []}

        spot_series = data['spot']
        iv_series = data['iv']
        rv_series = data['rv']
        
        # Valid Dates
        valid_dates = spot_series.index
        valid_dates = [d for d in valid_dates if d >= self.start_date and d <= self.end_date]
        
        trades = []
        history = []
        
        print(f"Running backtest on {len(valid_dates)} days...")
        
        for i, current_date in enumerate(valid_dates):
            # Check for end of data
            if i + 30 >= len(valid_dates):
                 break
                 
            # Build State
            state = self.builder.build_daily_state(
                self.symbol, current_date, spot_series, iv_series, rv_series
            )
            
            if not state: continue
            
            # Tokenize
            tokens = Tokenizer.get_tokens(state)
            
            # Canonical Signature
            token_sig = TokenSignature.create(tokens)
            
            # Log History for UI
            history.append({
                "date": current_date,
                "spot": state.spot_price,
                "iv_bucket": state.iv_bucket.name,
                "trend_strength": state.trend_strength.name,
                "tokens": tokens
            })
            
            # Check Strategies
            for strat in strategies_to_test:
                reasoning = []
                should_trade = False
                
                # Check Entry Loop
                if strat.should_enter(tokens):
                    should_trade = True
                    reasoning.append(f"Tokens {tokens} matched filter.")
                else:
                    reasoning.append(f"Tokens {tokens} did not match filter.")
                
                if should_trade:
                    # Simulate Trade
                    result = self.simulate_trade(strat, spot_series, i, current_date)
                    
                    # Update Belief
                    self.db.update_belief(strat.name, token_sig, result['win'])
                    
                    # Log Trade
                    state_dict = state.to_dict()
                    
                    trades.append({
                        "date": current_date,
                        "strategy": strat.name,
                        "tokens": tokens,
                        "result": result,
                        "state_snapshot": state_dict,
                        "reasoning": "; ".join(reasoning)
                    })
                    
        return {
            "trades": trades,
            "history": history
        }

    def simulate_trade(self, strategy: BaseStrategy, spot_series, current_idx, current_date) -> Dict:
        """
        Simulates trade outcome based on future price movement.
        Simplified PnL logic.
        """
        exit_cond = strategy.get_exit_conditions()
        max_days = exit_cond.get('max_days', 10)
        
        entry_price = spot_series.iloc[current_idx]
        
        # Look ahead
        future_prices = spot_series.iloc[current_idx+1 : current_idx+max_days+1]
        
        if future_prices.empty:
            return {"pnl": 0, "win": False, "roi": 0}
            
        exit_price = future_prices.iloc[-1]
        
        pnl = 0.0
        
        # Logic per strategy type (Approximation)
        if "Debit Spread" in strategy.name:
            if "Bull" in strategy.name:
                pnl = exit_price - entry_price
            else:
                pnl = entry_price - exit_price
                
        elif "Straddle" in strategy.name:
            # Long Straddle: Profit if moves away from entry
            move = abs(exit_price - entry_price)
            # Breakeven approx: needs to move > 1-2%? 
            # Let's say 2% move is required to cover premium
            premium_cost = entry_price * 0.02 
            pnl = move - premium_cost
            
        elif "Iron Condor" in strategy.name:
            # Short IC: Profit if stays within range
            # Assume entry wings are +/- 5%
            upper = entry_price * 1.05
            lower = entry_price * 0.95
            
            max_pnl_potential = entry_price * 0.01 # Collected premium approx
            
            # Did it breach?
            breached = ((future_prices > upper) | (future_prices < lower)).any()
            
            if breached:
                pnl = -max_pnl_potential * 2 # Loss
            else:
                pnl = max_pnl_potential # Max Profit
                
        win = pnl > 0
        return {"pnl": pnl, "win": win, "roi": (pnl/entry_price)*100}

if __name__ == "__main__":
    # Test Backtest
    be = BacktestEngine("NIFTY", date.today() - timedelta(days=60), date.today())
    results = be.run(strategies.get_all_strategies())
    
    print(f"\nBacktest Complete. Total Trades: {len(results['trades'])}")
    if results['trades']:
        df = pd.DataFrame(results['trades'])
        print(df[['date', 'strategy', 'result']].head())
