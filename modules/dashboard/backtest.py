"""Vectorized options backtest.

Every strategy is simulated on *every* day ("shadow trades"): legs priced with
Black-Scholes at entry IV, settled at intrinsic value after `hold_days` trading
days. The rule-based entries are the subset flagged `is_signal`. Shadow trades
give the context model dense, unbiased training data; signals are what a
rules-only trader would have taken.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from modules.ml.tokens import SLOTS, Tokenizer
from modules.utils import TRADING_DAYS, bs_price
from .market_state import build_feature_frame
from .strategy import STRATEGIES, Strategy

SLIPPAGE = 0.03  # fraction of gross premium lost to spreads/fees per round trip


@dataclass
class BacktestResult:
    features: pd.DataFrame
    tokens: pd.DataFrame
    trades: pd.DataFrame  # all shadow trades; `is_signal` marks rule entries


def price_strategy(strategy: Strategy, s0, st, iv):
    """Per-unit PnL, capital at risk and ROI% for arrays of entries. Returns dict of arrays."""
    t = strategy.hold_days / TRADING_DAYS
    move = iv / 100 * np.sqrt(t)
    entry_cost = np.zeros_like(s0)  # >0 debit, <0 credit
    gross = np.zeros_like(s0)
    strikes = []
    for leg in strategy.legs:
        k = s0 * np.exp(leg.k * move)
        prem = bs_price(leg.flag, s0, k, t, iv / 100)
        entry_cost += leg.qty * prem
        gross += prem
        strikes.append((leg, k))

    def settle(price):
        value = np.zeros_like(s0)
        for leg, k in strikes:
            intrinsic = np.maximum(price - k, 0) if leg.flag == "c" else np.maximum(k - price, 0)
            value += leg.qty * intrinsic
        return value

    # Worst case over a payoff-kink grid (payoffs are piecewise linear; all our structures are bounded).
    probes = [np.zeros_like(s0), s0 * 10] + [k for _, k in strikes]
    worst_value = np.min([settle(p) for p in probes], axis=0)
    risk = np.maximum(entry_cost - worst_value, 1e-9)

    pnl = settle(st) - entry_cost - SLIPPAGE * gross
    return {"pnl": pnl, "risk": risk, "roi": pnl / risk * 100, "premium": entry_cost}


class BacktestEngine:
    def __init__(self, symbol: str, market_df: pd.DataFrame, strategies=None):
        self.symbol = symbol
        self.market_df = market_df
        self.strategies = strategies or STRATEGIES

    def run(self) -> BacktestResult:
        features = build_feature_frame(self.market_df)
        tokens = Tokenizer.tokenize_frame(features)
        if tokens.empty:
            return BacktestResult(features, tokens, pd.DataFrame())

        token_lists = tokens[SLOTS].to_numpy().tolist()
        token_sets = [set(t) for t in token_lists]
        signatures = [Tokenizer.signature(t) for t in token_lists]
        pos = features.index.get_indexer(tokens.index)  # positions in the full series (exit lookup)
        close = features["close"].to_numpy(float)
        iv = features["iv"].to_numpy(float)[pos]
        s0 = close[pos]

        frames = []
        for strat in self.strategies:
            exit_pos = pos + strat.hold_days
            open_mask = exit_pos < len(close)  # exit must exist; trailing entries are still open
            if not open_mask.any():
                continue
            st = close[exit_pos[open_mask]]
            priced = price_strategy(strat, s0[open_mask], st, iv[open_mask])
            idx = np.flatnonzero(open_mask)
            frames.append(pd.DataFrame({
                "date": tokens.index[idx],
                "exit_date": features.index[exit_pos[open_mask]],
                "strategy": strat.name,
                "tokens": [token_lists[i] for i in idx],
                "signature": [signatures[i] for i in idx],
                "spot": s0[open_mask],
                "exit_spot": st,
                "iv": iv[open_mask],
                "premium": priced["premium"],
                "pnl": priced["pnl"],
                "roi": priced["roi"],
                "win": priced["pnl"] > 0,
                "is_signal": [strat.should_enter(token_sets[i]) for i in idx],
            }))
        trades = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not trades.empty:
            trades.insert(0, "symbol", self.symbol)
        return BacktestResult(features, tokens, trades)


def strategy_stats(trades: pd.DataFrame) -> pd.DataFrame:
    """Per-strategy summary: trades, win rate, avg ROI, cumulative ROI and max drawdown (in ROI points)."""
    rows = []
    for name, g in trades.groupby("strategy", sort=False):
        g = g.sort_values("date")
        equity = g["roi"].cumsum()
        rows.append({
            "Strategy": name,
            "Trades": len(g),
            "Win rate": g["win"].mean() * 100,
            "Avg ROI %": g["roi"].mean(),
            "Total ROI %": equity.iloc[-1],
            "Max DD %": (equity - equity.cummax()).min(),
        })
    return pd.DataFrame(rows)
