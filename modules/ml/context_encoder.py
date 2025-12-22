import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Dict, Tuple, Optional

class TokenVocabulary:
    """
    Maps string tokens to integer IDs.
    """
    def __init__(self):
        # Predefined vocabulary based on known buckets/tokens
        self.output_tokens = [
            "PAD", "UNK", "CLS", # Special tokens
            
            # Trend
            "TRENDING_UP", "TRENDING_DOWN", "RANGE_BOUND",
            "WEAK", "MODERATE", "STRONG",
            
            # Volatility
            "VOL_LOW", "VOL_MID", "VOL_HIGH", "VOL_EXTREME",
            
            # VRP
            "POSITIVE_VRP", "NEGATIVE_VRP", "NEUTRAL_VRP",
            
            # Events / External
            "EARNINGS_SOON", "MACRO_EVENT",
            "SENTIMENT_BULLISH", "SENTIMENT_BEARISH",
            "Attention_SPIKE"
        ]
        
        self.token_to_id = {t: i for i, t in enumerate(self.output_tokens)}
        self.id_to_token = {i: t for i, t in enumerate(self.output_tokens)}
        
    def get_id(self, token: str) -> int:
        return self.token_to_id.get(token, self.token_to_id["UNK"])
        
    def encode(self, tokens: List[str]) -> torch.Tensor:
        # Prepend CLS? Maybe useful for global context
        ids = [self.get_id("CLS")] + [self.get_id(t) for t in tokens]
        return torch.tensor(ids, dtype=torch.long)
        
    def size(self) -> int:
        return len(self.output_tokens)

class MicroTransformer(nn.Module):
    """
    A lightweight, encoder-only transformer to learn attention weights.
    Structure: Embedding -> MultiHeadAttention -> Norm -> FeedForward -> Norm
    """
    def __init__(self, vocab_size: int, embed_dim=32, num_heads=2, hidden_dim=64):
        super().__init__()
        self.embed_dim = embed_dim
        
        # 1. Embedding
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        
        # 2. Self Attention
        self.attention = nn.MultiheadAttention(embed_dim, num_heads, batch_first=True)
        self.ln1 = nn.LayerNorm(embed_dim)
        
        # 3. Feed Forward
        self.ff = nn.Sequential(
            nn.Linear(embed_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, embed_dim)
        )
        self.ln2 = nn.LayerNorm(embed_dim)
        
        # 4. Context Head (Optional, if we want to predict relevance score directly)
        # But Phase 4 goal is primarily "Attention Weights".
        
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        x: (Batch, Seq_Len)
        Returns: 
        - encoded: (Batch, Seq_Len, Embed_Dim)
        - attn_weights: (Batch, Seq_Len, Seq_Len)
        """
        # Embed
        emb = self.embedding(x) # (B, S, E)
        
        # Self Attention
        # attn_output: (B, S, E), weights: (B, S, S)
        attn_output, attn_weights = self.attention(emb, emb, emb)
        
        # Residual + Norm
        x = self.ln1(emb + attn_output)
        
        # Feed Forward
        ff_output = self.ff(x)
        
        # Residual + Norm
        x = self.ln2(x + ff_output)
        
        return x, attn_weights

class ContextEncoder:
    """
    Wrapper to easily use the model with our system.
    """
    def __init__(self):
        self.vocab = TokenVocabulary()
        self.model = MicroTransformer(self.vocab.size())
        self.model.eval() # Default to eval mode
        
    def get_attention(self, tokens: List[str]) -> Dict[str, float]:
        """
        Returns mapping of Token -> Attention Score.
        Score is derived from the CLS token's attention to other tokens.
        """
        if not tokens:
            return {}
            
        with torch.no_grad():
            # Encode
            input_ids = self.vocab.encode(tokens).unsqueeze(0) # (1, Seq+1)
            
            # Forward
            _, attn_weights = self.model(input_ids) # (1, S+1, S+1)
            
            # Extract CLS attention row (index 0) to others (indices 1..S)
            # attn_weights[0, 0, 1:] -> Batch 0, Row 0 (CLS), Cols 1..S (Tokens)
            # Note: MultiheadAttention averages weights across heads if return_attn_weights=True?
            # Actually nn.MultiheadAttention returns averaged weights.
            
            cls_attention = attn_weights[0, 0, 1:] # Exclude CLS itself (index 0)
            
            # Normalize? They sum to < 1 because CLS attends to itself too.
            # Let's normalize relative to the token set.
            if cls_attention.sum() > 0:
                cls_attention = cls_attention / cls_attention.sum()
                
            scores = cls_attention.tolist()
            
            return {t: s for t, s in zip(tokens, scores)}
            
    def save(self, path="context_encoder.pth"):
        torch.save(self.model.state_dict(), path)
        
    def load(self, path="context_encoder.pth"):
        try:
            self.model.load_state_dict(torch.load(path))
            self.model.eval()
        except FileNotFoundError:
            print("No trained model found. Using random weights (untrained).")
