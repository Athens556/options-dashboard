import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from typing import List, Tuple, Dict
from .context_encoder import ContextEncoder
from .train_data_builder import TrainingDatasetBuilder
from modules.dashboard.backtest import BacktestEngine
from modules.dashboard import strategy as strategies
from datetime import date, timedelta
import random

class Trainer:
    def __init__(self):
        self.encoder = ContextEncoder()
        self.dataset_builder = TrainingDatasetBuilder(None)
        
    def generate_data(self, symbol="NIFTY", days=365):
        print("Generating Training Data via Backtest...")
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        engine = BacktestEngine(symbol, start_date, end_date)
        # Run with ALL strategies to get maximum signal coverage
        output = engine.run(strategies.get_all_strategies())
        
        trades = output['trades']
        print(f"Generated {len(trades)} trades for training.")
        
        examples = self.dataset_builder.build_from_backtest_results(trades)
        return examples
        
    def train_from_trades(self, trades: List[Dict], epochs=5, lr=0.01) -> List[str]:
        """
        Trains the model using the provided list of trades.
        Returns a list of log messages.
        """
        logs = []
        if not trades:
            msg = "No trades provided for training."
            print(msg)
            logs.append(msg)
            return logs
            
        logs.append(f"Building dataset from {len(trades)} trades...")
        examples = self.dataset_builder.build_from_backtest_results(trades)
        
        if not examples:
            msg = "No valid training examples extracted."
            print(msg)
            logs.append(msg)
            return logs
            
        logs.append(f"Derived {len(examples)} training contexts (Token Sets).")
        
        model = self.encoder.model
        model.train()
        optimizer = optim.Adam(model.parameters(), lr=lr)
        # criteria = nn.MSELoss() # Changed to MSE as in previous step
        
        logs.append(f"Starting Training ({epochs} Epochs)...")
        print(f"Starting Training (Epochs: {epochs}, Samples: {len(examples)})...")
        
        initial_loss = 0
        final_loss = 0
        
        for epoch in range(epochs):
            total_loss = 0
            random.shuffle(examples)
            
            for tokens, target_map in examples:
                if not tokens: continue
                
                # Prepare Inputs (Batch=1)
                # Phase 4.5: Narrative Dropout
                # With p=0.3, mask NARRATIVE_PRESENT to NARRATIVE_UNCERTAIN
                # This forces model to learn from core market state even if narrative exists.
                train_tokens = list(tokens) # Copy
                if "NARRATIVE_PRESENT" in train_tokens and random.random() < 0.3:
                    train_tokens = [t if t != "NARRATIVE_PRESENT" else "NARRATIVE_UNCERTAIN" for t in train_tokens]
                
                input_ids = self.encoder.vocab.encode(train_tokens).unsqueeze(0)
                
                # Prepare Targets
                target_vals = [0.0] # CLS
                for t in train_tokens: # Use modified tokens for target mapping check
                    target_vals.append(target_map.get(t, 0.0))
                
                target_tensor = torch.tensor(target_vals).unsqueeze(0) # (1, S)
                
                optimizer.zero_grad()
                
                # Forward
                _, attn_weights = model(input_ids) # (1, S, S)
                
                # Extract CLS row: (1, S)
                cls_attn = attn_weights[:, 0, :] 
                
                # Align sizes (just in case)
                if cls_attn.shape != target_tensor.shape:
                     pass

                # Core Loss (Belief Alignment)
                main_loss = F.mse_loss(cls_attn, target_tensor)
                
                # Phase 4.5: Narrative Awareness Aux Loss
                # If NARRATIVE_PRESENT is in tokens, ensure it has non-zero attention.
                # Penalty = max(0, 0.1 - attn_weight)
                aux_loss = 0.0
                if "NARRATIVE_PRESENT" in tokens:
                    # Find index
                    try:
                        idx = tokens.index("NARRATIVE_PRESENT") + 1 # +1 for CLS offset
                        attn_val = cls_attn[0, idx]
                        # We want attn_val > 0.1 (Awareness Threshold)
                        # If attn_val is 0.05, penalty is 0.05.
                        aux_loss = torch.relu(0.1 - attn_val)
                    except:
                        pass
                
                loss = main_loss + (0.5 * aux_loss)
                
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
                
            avg_loss = total_loss / len(examples)
            
            if epoch == 0: initial_loss = avg_loss
            final_loss = avg_loss
            
            # log_msg = f"Epoch {epoch+1}/{epochs} | Loss: {avg_loss:.4f}"
            # print(log_msg)
            # logs.append(log_msg)
            
        logs.append(f"Training Complete. Loss Delta: {initial_loss:.4f} -> {final_loss:.4f}")
        print("Training Complete.")
        
        self.encoder.save()
        logs.append("Model weights updated and saved.")
        return logs

    def train(self, examples: List[Tuple[List[str], Dict[str, float]]], epochs=5, lr=0.01):
        # Legacy method wrapper
        # We can implement it similar to above or just ignore since we use train_from_trades
        pass

if __name__ == "__main__":
    trainer = Trainer()
    # User Request: SBIN for past year
    data = trainer.generate_data(symbol="SBIN", days=365)
    trainer.train(data)
