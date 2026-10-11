"""Mini tokenizer: turns each day's continuous market features into a fixed-length
"sentence" of 7 discrete tokens, one per slot.

Fixed slots mean every day has the same shape (no padding), each token has a
known slot (the model gets a slot embedding), and tokens stay human-readable.
"""
from typing import Dict, List

import numpy as np
import pandas as pd

# slot -> (feature column, bin edges, token per bin). Bins are right-open: edges[i] <= x < edges[i+1].
SLOT_SPECS = {
    "TREND": ("trend_z", [-1.0, -0.35, 0.35, 1.0],
              ["TREND_STRONG_DOWN", "TREND_DOWN", "TREND_FLAT", "TREND_UP", "TREND_STRONG_UP"]),
    "MOMENTUM": ("mom_z", [-0.75, 0.75], ["MOM_DOWN", "MOM_FLAT", "MOM_UP"]),
    "IV_LEVEL": ("iv_pct", [20, 50, 80], ["IV_LOW", "IV_MID", "IV_HIGH", "IV_EXTREME"]),
    "IV_FLOW": ("iv_chg5", [-8, 8], ["IV_FALLING", "IV_STABLE", "IV_RISING"]),
    "VRP": ("vrp_ratio", [0.95, 1.2], ["VRP_CHEAP", "VRP_FAIR", "VRP_RICH"]),
    "RV_REGIME": ("rv_ratio", [0.83, 1.2], ["RV_CONTRACTING", "RV_STEADY", "RV_EXPANDING"]),
    "VIX": ("vix_pct", [33, 67], ["VIX_LOW", "VIX_MID", "VIX_HIGH"]),
}
SLOTS: List[str] = list(SLOT_SPECS)
OPTIONAL_TOKENS = {"VIX": "VIX_NA"}  # slots that may be missing emit a placeholder instead of dropping the day
CORE_SLOTS = ("TREND", "IV_LEVEL", "VRP")  # coarse key for Bayesian beliefs (dense enough to accumulate)

VOCAB_BY_SLOT: Dict[str, List[str]] = {
    slot: tokens + ([OPTIONAL_TOKENS[slot]] if slot in OPTIONAL_TOKENS else [])
    for slot, (_, _, tokens) in SLOT_SPECS.items()
}
ALL_TOKENS: List[str] = [t for toks in VOCAB_BY_SLOT.values() for t in toks]
TOKEN_SLOT: Dict[str, str] = {t: s for s, toks in VOCAB_BY_SLOT.items() for t in toks}

EXPLANATIONS = {
    "TREND_STRONG_UP": "20D MA well above 50D MA (>1σ of 20D moves)",
    "TREND_UP": "20D MA above 50D MA",
    "TREND_FLAT": "MAs converged — price is ranging",
    "TREND_DOWN": "20D MA below 50D MA",
    "TREND_STRONG_DOWN": "20D MA well below 50D MA (>1σ of 20D moves)",
    "MOM_UP": "5-day return above +0.75σ",
    "MOM_FLAT": "5-day return within ±0.75σ",
    "MOM_DOWN": "5-day return below −0.75σ",
    "IV_LOW": "IV in bottom 20% of its 1-year range",
    "IV_MID": "IV in the 20–50th percentile",
    "IV_HIGH": "IV in the 50–80th percentile",
    "IV_EXTREME": "IV in top 20% of its 1-year range",
    "IV_RISING": "IV up >8% over 5 days",
    "IV_STABLE": "IV within ±8% over 5 days",
    "IV_FALLING": "IV down >8% over 5 days",
    "VRP_RICH": "IV > 1.2× realized vol — options are expensive",
    "VRP_FAIR": "IV roughly equal to realized vol",
    "VRP_CHEAP": "IV < 0.95× realized vol — options are cheap",
    "RV_EXPANDING": "10D realized vol > 1.2× 30D — moves are getting bigger",
    "RV_STEADY": "Realized vol stable",
    "RV_CONTRACTING": "10D realized vol < 0.83× 30D — market is calming",
    "VIX_LOW": "India VIX in bottom third of its 1-year range",
    "VIX_MID": "India VIX mid-range",
    "VIX_HIGH": "India VIX in top third of its 1-year range",
    "VIX_NA": "No India VIX data",
}


class Tokenizer:
    @staticmethod
    def tokenize_frame(features: pd.DataFrame) -> pd.DataFrame:
        """One column per slot, one row per day. Days in feature warm-up (NaN core features) are dropped."""
        cols = {}
        for slot, (feature, edges, tokens) in SLOT_SPECS.items():
            x = features[feature].to_numpy(dtype=float)
            labels = np.asarray(tokens, dtype=object)[np.digitize(x, edges)]
            labels[np.isnan(x)] = OPTIONAL_TOKENS.get(slot)
            cols[slot] = labels
        out = pd.DataFrame(cols, index=features.index)
        required = [s for s in SLOTS if s not in OPTIONAL_TOKENS]
        return out.dropna(subset=required)

    @staticmethod
    def get_tokens(token_row) -> List[str]:
        return [token_row[s] for s in SLOTS]

    @staticmethod
    def signature(tokens: List[str], slots=CORE_SLOTS) -> str:
        return "+".join(t for t in tokens if TOKEN_SLOT.get(t) in slots)

    @staticmethod
    def explain_token(token: str) -> str:
        return EXPLANATIONS.get(token, "No description available")
