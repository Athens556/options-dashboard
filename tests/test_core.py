"""Offline tests for the features -> tokens -> backtest -> model pipeline (synthetic data, no network).

Run: python -m pytest tests/test_core.py -q
"""
import numpy as np
import pandas as pd
import pytest

from modules import utils
from modules.api import data_loader
from modules.dashboard.backtest import BacktestEngine, strategy_stats
from modules.dashboard.db_manager import DBManager
from modules.dashboard.market_state import build_feature_frame, causality_audit
from modules.ml.tokens import ALL_TOKENS, SLOTS, Tokenizer


def synthetic_market(n=500, seed=7) -> pd.DataFrame:
    return data_loader.synthetic_market(symbol=f"SYN{seed}", end_date="2025-06-30", n=n)


def test_iv_solver_round_trips_black_scholes():
    s, k, t = np.array([100.0, 100.0, 250.0]), np.array([100.0, 110.0, 240.0]), np.array([0.1, 0.5, 0.05])
    sigma = np.array([0.15, 0.4, 0.25])
    for flag in ("c", "p"):
        price = utils.bs_price(flag, s, k, t, sigma, 0.06)
        iv = utils.calculate_iv(price, s, k, t, 0.06, flag)
        np.testing.assert_allclose(iv, sigma * 100, atol=1e-3)


def test_rolling_percentile_matches_naive():
    s = pd.Series(np.random.default_rng(0).normal(size=300))
    fast = utils.rolling_percentile(s, window=50, min_periods=25)
    naive = s.rolling(50, min_periods=25).apply(lambda x: (x[:-1] < x[-1]).sum() / len(x) * 100, raw=True)
    np.testing.assert_allclose(fast.to_numpy(), naive.to_numpy(), equal_nan=True)


def test_features_are_causal():
    assert causality_audit(synthetic_market(), n_checks=8)


def test_tokenizer_emits_one_known_token_per_slot():
    tokens = Tokenizer.tokenize_frame(build_feature_frame(synthetic_market()))
    assert list(tokens.columns) == SLOTS
    assert len(tokens) > 300
    assert set(np.unique(tokens.to_numpy())) <= set(ALL_TOKENS)


def test_backtest_shadow_trades_and_signals():
    result = BacktestEngine("SYN", synthetic_market()).run()
    trades = result.trades
    assert not trades.empty
    assert (trades["exit_date"] > trades["date"]).all()
    assert trades["is_signal"].any() and not trades["is_signal"].all()
    # every trade's risk is bounded: ROI can never be below -100% (plus slippage)
    assert trades["roi"].min() > -110
    stats = strategy_stats(trades)
    assert set(stats["Strategy"]) == set(trades["strategy"])


def test_db_upsert_is_idempotent(tmp_path):
    db = DBManager(str(tmp_path / "t.db"))
    trades = BacktestEngine("SYN", synthetic_market()).run().trades
    db.upsert_trades(trades)
    db.upsert_trades(trades)  # re-running a backtest must not double-count beliefs
    assert db.trade_count() == len(trades)
    sig = trades["signature"].iloc[0]
    wins_losses = db.beliefs("SYN", sig)
    expected = trades[trades["signature"] == sig].groupby("strategy")["win"].agg(["sum", "count"])
    for name, (w, l) in wins_losses.items():
        assert w == expected.loc[name, "sum"] and w + l == expected.loc[name, "count"]
    loaded = db.load_trades("SYN").set_index(["strategy", "date"]).sort_index()
    original = trades.set_index(["strategy", "date"]).sort_index()
    assert loaded["tokens"].tolist() == original["tokens"].tolist()


def test_model_trains_and_explains(tmp_path, monkeypatch):
    torch = pytest.importorskip("torch")
    from modules.ml import context_encoder
    from modules.ml.trainer import Trainer
    monkeypatch.setattr(context_encoder, "MODEL_PATH", str(tmp_path / "m.pt"))
    monkeypatch.setattr(context_encoder.ContextEncoder.save, "__defaults__", (str(tmp_path / "m.pt"),))
    monkeypatch.setattr(context_encoder.ContextEncoder.load, "__defaults__", (str(tmp_path / "m.pt"),))

    trades = BacktestEngine("SYN", synthetic_market(n=700)).run().trades
    trainer = Trainer()
    report = trainer.fit(trades, max_epochs=120)
    assert report.n_val > 0 and 0 <= report.val_auc <= 1
    assert report.train_curve[-1] < report.train_curve[0]

    tokens = trades["tokens"].iloc[-1]
    exp = trainer.encoder.explain(tokens, "Iron Condor")
    assert 0 < exp["p"] < 1
    assert set(exp["attention"]) == set(tokens)
    assert abs(sum(exp["attention"].values()) - 1) < 1e-5

    fresh = context_encoder.ContextEncoder()
    assert fresh.load() and fresh.trained
    np.testing.assert_allclose(fresh.explain(tokens, "Iron Condor")["p"], exp["p"], rtol=1e-5)


def test_bhavcopy_atm_iv_recovers_known_vol():
    days = pd.bdate_range("2025-01-06", periods=5)
    spot = pd.Series([100.0, 101.0, 99.0, 102.0, 100.5], index=days)
    rows = []
    for d, s in spot.items():
        for expiry in (pd.Timestamp("2025-01-30"), pd.Timestamp("2025-02-27")):
            t = (expiry - d).days / 365
            for k in (95.0, 100.0, 105.0):
                for flag, typ in (("c", "CE"), ("p", "PE")):
                    price = float(utils.bs_price(flag, s, k, t, 0.2, 0.06))
                    rows.append({"TIMESTAMP": d.date(), "STRIKE_PR": k, "EXPIRY_DT": expiry,
                                 "OPTION_TYP": typ, "CLOSE": price})
    iv = data_loader.compute_atm_iv(pd.DataFrame(rows), spot)
    assert list(iv.index) == list(days)
    np.testing.assert_allclose(iv.to_numpy(), 20.0, atol=1e-3)
