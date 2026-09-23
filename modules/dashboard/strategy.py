"""Strategies = entry rule over tokens + option legs with strikes in σ-units of the expected move.

Strike K = S0 · exp(k · σ√T), where σ is entry IV and T the holding period, so a
"1σ" wing adapts to each symbol's volatility on each day.
"""
from dataclasses import dataclass
from typing import Callable, List, Set


@dataclass(frozen=True)
class Leg:
    flag: str   # 'c' or 'p'
    k: float    # strike offset in σ-units of the expected move
    qty: int    # +1 long, -1 short


@dataclass(frozen=True)
class Strategy:
    name: str
    thesis: str
    legs: tuple
    hold_days: int
    rule: Callable[[Set[str]], bool]

    def should_enter(self, tokens) -> bool:
        return bool(self.rule(set(tokens)))


def _iron_condor(t):
    return ({"TREND_FLAT", "TREND_UP", "TREND_DOWN"} & t and {"IV_HIGH", "IV_EXTREME"} & t
            and "VRP_CHEAP" not in t)


def _long_straddle(t):
    return {"IV_LOW", "IV_MID"} & t and ({"VRP_CHEAP", "RV_EXPANDING"} & t)


def _bull_call(t):
    return {"TREND_UP", "TREND_STRONG_UP"} & t and "MOM_DOWN" not in t


def _bear_put(t):
    return {"TREND_DOWN", "TREND_STRONG_DOWN"} & t and "MOM_UP" not in t


STRATEGIES: List[Strategy] = [
    Strategy("Iron Condor", "Sell rich vol in a range: short ±1σ, long ±2σ wings",
             (Leg("c", 1.0, -1), Leg("c", 2.0, 1), Leg("p", -1.0, -1), Leg("p", -2.0, 1)), 20, _iron_condor),
    Strategy("Long Straddle", "Buy cheap vol before moves expand: long ATM call + put",
             (Leg("c", 0.0, 1), Leg("p", 0.0, 1)), 10, _long_straddle),
    Strategy("Bull Call Spread", "Ride uptrends: long ATM call, short +1σ call",
             (Leg("c", 0.0, 1), Leg("c", 1.0, -1)), 15, _bull_call),
    Strategy("Bear Put Spread", "Ride downtrends: long ATM put, short −1σ put",
             (Leg("p", 0.0, 1), Leg("p", -1.0, -1)), 15, _bear_put),
]
STRATEGY_NAMES = [s.name for s in STRATEGIES]


def get_all_strategies() -> List[Strategy]:
    return list(STRATEGIES)
