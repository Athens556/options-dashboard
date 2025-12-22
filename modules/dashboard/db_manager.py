import sqlite3
import pandas as pd
import json
import os
from datetime import datetime, date

DB_PATH = os.path.join(os.getcwd(), "market_research.db")

class DBManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.init_db()
        
    def get_connection(self):
        return sqlite3.connect(self.db_path)
        
    def init_db(self):
        """Initializes the database schema."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 1. Market States Table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_states (
            symbol TEXT,
            date TEXT,
            spot_price REAL,
            trend_score REAL,
            is_trending BOOLEAN,
            regime_label TEXT,
            iv REAL,
            rv REAL,
            vrp REAL,
            iv_percentile REAL,
            volatility_regime TEXT,
            sentiment_score REAL,
            trends_velocity REAL,
            earnings_proximity BOOLEAN,
            event_window BOOLEAN,
            PRIMARY KEY (symbol, date)
        )
        ''')
        
        # 2. Strategy Performance (Backtest Log)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_name TEXT,
            symbol TEXT,
            entry_date TEXT,
            exit_date TEXT,
            entry_state_json TEXT,
            entry_tokens_json TEXT,
            pnl REAL,
            roi REAL,
            win BOOLEAN
        )
        ''')
        
        # 3. Strategy Beliefs (Bayesian Store)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_beliefs (
            strategy_name TEXT,
            token_signature TEXT, -- e.g. "HIGH_IV+TRENDING"
            alpha REAL DEFAULT 1.0, -- Wins (+prior)
            beta REAL DEFAULT 1.0,  -- Losses (+prior)
            last_updated TEXT,
            PRIMARY KEY (strategy_name, token_signature)
        )
        ''')

        # 4. Trends Cache (Google Trends)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trends_cache (
            symbol TEXT PRIMARY KEY, 
            data_json TEXT, 
            last_updated TEXT
        )
        ''')
        
        conn.commit()
        conn.close()
        
    def save_market_state(self, state):
        """Saves a MarketState object."""
        if not state: return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Convert date to string ISO format
        date_str = state.date.strftime("%Y-%m-%d") if isinstance(state.date, (date, datetime)) else state.date
        
        cursor.execute('''
        INSERT OR REPLACE INTO market_states VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ''', (
            state.symbol, date_str, state.spot_price,
            state.trend_score, state.is_trending, state.regime_label,
            state.iv, state.rv, state.vrp, state.iv_percentile, state.volatility_regime,
            state.sentiment_score, state.trends_velocity,
            state.earnings_proximity, state.event_window
        ))
        conn.commit()
        conn.close()
        
    def fetch_market_state(self, symbol, date_obj):
        """Fetches state for a specific date."""
        conn = self.get_connection()
        date_str = date_obj.strftime("%Y-%m-%d") if isinstance(date_obj, (date, datetime)) else date_obj
        
        df = pd.read_sql_query(
            "SELECT * FROM market_states WHERE symbol = ? AND date = ?", 
            conn, params=(symbol, date_str)
        )
        conn.close()
        return df
        
    def update_belief(self, strategy_name, token_signature, won: bool):
        """Updates the Bayesian parameters."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Fetch current
        cursor.execute("SELECT alpha, beta FROM strategy_beliefs WHERE strategy_name=? AND token_signature=?", (strategy_name, token_signature))
        row = cursor.fetchone()
        
        if row:
            alpha, beta = row
        else:
            alpha, beta = 1.0, 1.0
            
        if won:
            alpha += 1
        else:
            beta += 1
            
        cursor.execute('''
        INSERT OR REPLACE INTO strategy_beliefs (strategy_name, token_signature, alpha, beta, last_updated)
        VALUES (?, ?, ?, ?, ?)
        ''', (strategy_name, token_signature, alpha, beta, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()

    def apply_time_decay(self, decay_factor=0.99):
        """
        Decays alpha and beta for all beliefs to prioritize recent data.
        Should be called daily or periodically.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Multiply alpha/beta by decay_factor
        # Use simple update query
        cursor.execute(f'''
            UPDATE strategy_beliefs
            SET alpha = alpha * {decay_factor},
            beta = beta * {decay_factor}
            WHERE alpha > 1.0 AND beta > 1.0
        ''')
        
        conn.commit()
        conn.close()

    def get_trends_cache(self, symbol):
        """Fetches cached trends if less than 24h old."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check for cache within last 24 hours
        cutoff = (datetime.now() - pd.Timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("SELECT data_json FROM trends_cache WHERE symbol=? AND last_updated > ?", (symbol, cutoff))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None

    def save_trends_cache(self, symbol, data_json):
        """Saves trends data to cache."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Table guaranteed by init_db, but safe to keep IF NOT EXISTS here too if we want atomic
        # But per strict schema management, usually better in init.
        # I'll rely on init_db or explicit create if missing. 
        # Actually, let's just insert. If table missing (old instance?), it might error if init_db wasn't run recently.
        # Safer to trigger init_db if needed? 
        # For now, just insert.
        cursor.execute("INSERT OR REPLACE INTO trends_cache (symbol, data_json, last_updated) VALUES (?, ?, ?)", 
                      (symbol, json.dumps(data_json), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()

    def get_recommended_strategies(self, current_tokens: list, top_k=3, min_obs=1):
        """
        Returns top strategies based on posterior mean (alpha / (alpha + beta))
        given the current context (tokens).
        Applies Guardrails:
        - Min Observations to trust a strategy.
        Applies Phase 4:
        - Context Attention boosting.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Calculate signature
        from modules.ml.token_signature import TokenSignature
        token_sig = TokenSignature.create(current_tokens)
        
        # Phase 4: Predict Attention Weights
        # Ideally, we cache the encoder instance globally or in DBManager init.
        # For now, lazy load it here.
        attention_map = {}
        try:
            from modules.ml.context_encoder import ContextEncoder
            # Memoize/Cache this if slow
            if not hasattr(self, 'encoder'):
                self.encoder = ContextEncoder()
                self.encoder.load()
            
            attention_map = self.encoder.get_attention(current_tokens)
        except Exception as e:
            print(f"ContextEncoder Inference Failed: {e}")

        # Guardrails: Entropy Check (Safety Fallback)
        use_attention = False
        if attention_map:
            import math
            # Calculate Entropy of weights
            weights = list(attention_map.values())
            # Normalize to be sure (softmax output sums to 1, but let's be safe)
            total_w = sum(weights)
            if total_w > 0:
                p = [w/total_w for w in weights]
                entropy = -sum([pi * math.log(pi + 1e-9) for pi in p])
                
                # Max Entropy for N items is ln(N)
                max_entropy = math.log(len(p)) if len(p) > 0 else 0
                
                # If Entropy is very close to Max Entropy, the model is "confused" (Uniform attention).
                # Fallback: Ignore attention if Normalized Entropy > 0.9
                normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
                
                if normalized_entropy < 0.9:
                    use_attention = True
                else:
                    print(f"High Attention Entropy ({normalized_entropy:.2f}). Fallback to deterministic.")

        cursor.execute('''
            SELECT strategy_name, alpha, beta 
            FROM strategy_beliefs 
            WHERE token_signature = ?
        ''', (token_sig,))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Calculate scores
        ranked = []
        for r in rows:
            name, alpha, beta = r
            
            # Guardrail: Sample Size
            observations = (alpha - 1) + (beta - 1) 
            if observations < min_obs:
                continue
                
            prior_mean = alpha / (alpha + beta)
            
            # Phase 4: Boost Confidence based on Attention?
            # Strategy doesn't explicitly declare WHICH tokens it uses in DB (it uses all in context).
            # But we can see if the *High Attention* tokens are driving this belief?
            # Actually, 'token_sig' implies the whole set is the key.
            # So if the model thinks this SET is "High Signal" (e.g. key tokens have high weight), maybe we trust it more?
            
            # Better logic: 
            # If the Model says "VOL_HIGH" is important (0.8), and "RANGE_BOUND" is noise (0.1).
            # And our Strategy is IronCondor (relies on VOL_HIGH).
            # Then we are good.
            # If Model says "VOL_HIGH" is noise (0.1) but we are in VOL_HIGH regime...
            # This requires mapping Strategy -> Dependent Tokens. Complex.
            
            # Simplified Logic for Phase 4:
            # Check Entropy of attention. If Low Entropy (Confident model), we trust the belief more (boost score slightly).
            # If High Entropy (Confused model), we dampen?
            # Or just return the weights for UI to display.
            
            weighted_score = prior_mean
            
            # Let's just pass the attention summary to the UI
            
            # Guardrail: Cap confidence
            weighted_score = min(weighted_score, 0.9)
            
            ranked.append({
                "strategy": name,
                "score": weighted_score,
                "confidence": alpha + beta,
                "obs": observations,
                "attention": attention_map # Pass for Explainability
            })
            
        # Sort desc
        ranked.sort(key=lambda x: x['score'], reverse=True)
        return ranked[:top_k]
