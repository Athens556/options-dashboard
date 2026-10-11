"""Trains the context encoder on stored shadow trades.

Validation is chronological and purged: validation starts at the 75th-percentile
entry date, and training keeps only trades whose *exit* precedes it, so no
training label peeks into the validation window. The best epoch count is picked
on validation, then the model is refit on everything for live predictions.
"""
import copy
from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

from .context_encoder import ContextEncoder, MicroTransformer


def roc_auc(y: np.ndarray, p: np.ndarray) -> float:
    """Rank-based AUC (Mann-Whitney U). NaN when only one class is present."""
    pos, neg = y.sum(), len(y) - y.sum()
    if pos == 0 or neg == 0:
        return float("nan")
    ranks = pd.Series(p).rank().to_numpy()
    return float((ranks[y == 1].sum() - pos * (pos + 1) / 2) / (pos * neg))


@dataclass
class TrainReport:
    n_train: int = 0
    n_val: int = 0
    val_start: pd.Timestamp = None
    val_auc: float = float("nan")
    val_acc: float = float("nan")
    val_base_rate: float = float("nan")
    best_epoch: int = 0
    train_curve: List[float] = field(default_factory=list)
    val_curve: List[float] = field(default_factory=list)
    val_predictions: pd.DataFrame = None  # validation trades with out-of-sample `p_win`
    logs: List[str] = field(default_factory=list)


class Trainer:
    def __init__(self, encoder: ContextEncoder = None):
        self.encoder = encoder or ContextEncoder()

    def _tensors(self, trades: pd.DataFrame):
        """Collapse identical (strategy, sentence) rows into one row with soft label = win rate and
        weight = count. Weighted BCE on this is exactly the per-trade loss, at a fraction of the compute
        (the token space is small, so thousands of trades map to a few hundred unique sentences)."""
        key = trades["strategy"] + "|" + trades["tokens"].map("|".join)
        grouped = trades.assign(_key=key).groupby("_key", sort=False)
        first = grouped.head(1).set_index("_key")
        agg = grouped["win"].agg(["mean", "count"]).loc[first.index]
        x = self.encoder.vocab.encode_batch(first["tokens"].tolist(), first["strategy"].tolist())
        y = torch.tensor(agg["mean"].to_numpy(dtype=np.float32))
        w = torch.tensor(agg["count"].to_numpy(dtype=np.float32))
        return x, y, w

    @staticmethod
    def _loss(logits, y, w):
        return (F.binary_cross_entropy_with_logits(logits, y, reduction="none") * w).sum() / w.sum()

    def _run(self, x, y, w, epochs, lr, weight_decay, val=None, seed=0, patience=30):
        torch.manual_seed(seed)  # fresh, seeded init per fit keeps runs reproducible
        model = self.encoder.model = MicroTransformer(self.encoder.vocab.size())
        opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
        train_curve, val_curve = [], []
        best = (float("inf"), 0, None)
        for epoch in range(epochs):
            model.train()
            opt.zero_grad()
            logits, _ = model(x)
            loss = self._loss(logits, y, w)
            loss.backward()
            opt.step()
            train_curve.append(loss.item())
            if val is not None:
                model.eval()
                with torch.no_grad():
                    v = self._loss(model(val[0])[0], val[1], val[2]).item()
                val_curve.append(v)
                if v < best[0]:
                    best = (v, epoch + 1, copy.deepcopy(model.state_dict()))
                elif epoch + 1 - best[1] >= patience:
                    break  # early stop: validation hasn't improved for `patience` epochs
        return train_curve, val_curve, best

    def fit(self, trades: pd.DataFrame, max_epochs=300, lr=3e-3, weight_decay=1e-2, seed=0) -> TrainReport:
        report = TrainReport()
        trades = trades.sort_values("date").reset_index(drop=True)
        if len(trades) < 40:
            report.logs.append(f"Only {len(trades)} trades — need at least 40 to train.")
            return report

        val_start = trades["date"].quantile(0.75)
        train = trades[trades["exit_date"] < val_start]
        val = trades[trades["date"] >= val_start]
        epochs = 150
        if len(train) >= 40 and len(val) >= 20:
            train_curve, val_curve, (best_loss, best_epoch, best_state) = self._run(
                *self._tensors(train), max_epochs, lr, weight_decay, self._tensors(val), seed)
            self.encoder.model.load_state_dict(best_state)
            p = self.encoder.predict_proba(val["tokens"].tolist(), val["strategy"].tolist())
            yv_np = val["win"].to_numpy(dtype=float)
            report.n_train, report.n_val, report.val_start = len(train), len(val), val_start
            report.val_auc = roc_auc(yv_np, p)
            report.val_acc = float(((p > 0.5) == yv_np).mean())
            report.val_base_rate = float(max(yv_np.mean(), 1 - yv_np.mean()))
            report.best_epoch = epochs = max(best_epoch, 20)
            report.train_curve, report.val_curve = train_curve, val_curve
            report.val_predictions = val.assign(p_win=p)
            report.logs.append(
                f"Validation (from {val_start:%d %b %Y}): AUC {report.val_auc:.3f} · "
                f"accuracy {report.val_acc:.1%} vs {report.val_base_rate:.1%} majority baseline · "
                f"best epoch {best_epoch}")
        else:
            report.logs.append("Not enough history for a purged validation split — training on all data.")

        full_curve, _, _ = self._run(*self._tensors(trades), epochs, lr, weight_decay, seed=seed)
        if not report.train_curve:
            report.train_curve = full_curve
        self.encoder.model.eval()
        self.encoder.meta = {"trained": True, "n_trades": len(trades), "epochs": epochs,
                             "val_auc": report.val_auc, "val_acc": report.val_acc}
        self.encoder.save()
        report.logs.append(f"Refit on all {len(trades):,} trades for {epochs} epochs — weights saved.")
        return report
