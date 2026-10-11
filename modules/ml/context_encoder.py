"""Micro transformer over token sentences.

Input:  [CLS, STRAT:<name>, TREND_*, MOMENTUM_*, IV_LEVEL_*, IV_FLOW_*, VRP_*, RV_*, VIX_*]
Output: P(win) for that strategy in that market context, plus two explanations:
  - attention: how much CLS attends to each market token (what the model looks at)
  - impact:    change in P(win) when a token is masked to UNK (which way it pushes)

Conditioning on the strategy token means one model learns a different reading
of the same market per strategy.
"""
import os
from typing import Dict, List, Sequence

import numpy as np
import torch
import torch.nn as nn

from modules.dashboard.strategy import STRATEGY_NAMES
from .tokens import ALL_TOKENS, SLOTS

MODEL_DIR = os.path.join(os.getcwd(), "data", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "context_encoder.pt")
SEQ_LEN = 2 + len(SLOTS)
MARKET_OFFSET = 2  # market tokens start after CLS + STRAT

torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))


class TokenVocabulary:
    def __init__(self, strategies: Sequence[str] = STRATEGY_NAMES):
        self.tokens = ["PAD", "UNK", "CLS"] + [f"STRAT:{s}" for s in strategies] + ALL_TOKENS
        self.token_to_id = {t: i for i, t in enumerate(self.tokens)}
        self.unk = self.token_to_id["UNK"]

    def get_id(self, token: str) -> int:
        return self.token_to_id.get(token, self.unk)

    def encode_batch(self, token_lists: Sequence[Sequence[str]], strategies: Sequence[str]) -> torch.Tensor:
        cls = self.token_to_id["CLS"]
        rows = [[cls, self.get_id(f"STRAT:{s}")] + [self.get_id(t) for t in toks]
                for toks, s in zip(token_lists, strategies)]
        return torch.tensor(rows, dtype=torch.long)

    def size(self) -> int:
        return len(self.tokens)


class MicroTransformer(nn.Module):
    """Embedding + slot position -> one self-attention block -> CLS -> logit."""

    def __init__(self, vocab_size: int, seq_len=SEQ_LEN, embed_dim=32, num_heads=2, hidden_dim=64, dropout=0.1):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.position = nn.Parameter(torch.randn(seq_len, embed_dim) * 0.02)
        self.attention = nn.MultiheadAttention(embed_dim, num_heads, dropout=dropout, batch_first=True)
        self.ln1 = nn.LayerNorm(embed_dim)
        self.ff = nn.Sequential(nn.Linear(embed_dim, hidden_dim), nn.GELU(), nn.Dropout(dropout),
                                nn.Linear(hidden_dim, embed_dim))
        self.ln2 = nn.LayerNorm(embed_dim)
        self.head = nn.Linear(embed_dim, 1)

    def forward(self, x: torch.Tensor):
        h = self.embedding(x) + self.position
        attn_out, attn_weights = self.attention(h, h, h, need_weights=True, average_attn_weights=True)
        h = self.ln1(h + attn_out)
        h = self.ln2(h + self.ff(h))
        return self.head(h[:, 0]).squeeze(-1), attn_weights


class ContextEncoder:
    def __init__(self, seed: int = 0):
        torch.manual_seed(seed)
        self.vocab = TokenVocabulary()
        self.model = MicroTransformer(self.vocab.size())
        self.model.eval()
        self.meta: Dict = {}

    @property
    def trained(self) -> bool:
        return bool(self.meta.get("trained"))

    @torch.no_grad()
    def predict_proba(self, token_lists: Sequence[Sequence[str]], strategies: Sequence[str]) -> np.ndarray:
        self.model.eval()
        logits, _ = self.model(self.vocab.encode_batch(token_lists, strategies))
        return torch.sigmoid(logits).numpy()

    @torch.no_grad()
    def explain(self, tokens: List[str], strategy: str) -> Dict:
        """P(win), CLS attention over market tokens, and masking impact per token — one batched forward."""
        self.model.eval()
        base = self.vocab.encode_batch([tokens], [strategy])
        masked = base.repeat(len(tokens), 1)
        masked[torch.arange(len(tokens)), MARKET_OFFSET + torch.arange(len(tokens))] = self.vocab.unk
        logits, attn = self.model(torch.cat([base, masked]))
        probs = torch.sigmoid(logits).numpy()
        cls_attn = attn[0, 0, MARKET_OFFSET:].numpy()
        cls_attn = cls_attn / cls_attn.sum() if cls_attn.sum() > 0 else cls_attn
        return {
            "p": float(probs[0]),
            "attention": dict(zip(tokens, cls_attn.tolist())),
            "impact": dict(zip(tokens, (probs[0] - probs[1:]).tolist())),
        }

    def save(self, path=MODEL_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save({"state_dict": self.model.state_dict(), "vocab": self.vocab.tokens, "meta": self.meta}, path)

    def load(self, path=MODEL_PATH) -> bool:
        """Loads weights if present and built for the current vocabulary. Returns success."""
        if not os.path.exists(path):
            return False
        try:
            ckpt = torch.load(path, weights_only=True)
            if ckpt.get("vocab") != self.vocab.tokens:
                return False  # tokenizer changed since this checkpoint: retrain instead of mis-mapping ids
            self.model.load_state_dict(ckpt["state_dict"])
            self.meta = ckpt.get("meta", {})
            self.model.eval()
            return True
        except Exception as e:
            print(f"Could not load context encoder: {e}")
            return False
