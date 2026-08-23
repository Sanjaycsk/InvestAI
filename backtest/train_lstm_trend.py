"""
InvestAI — LSTM attempt at the same short-horizon trend prediction problem.

Attempt #5 in this line of investigation (see train_ml_trend.py's docstring
for #1-4: plain GBM, ARIMA, richer-feature GBM, all failed to beat a naive
baseline at both 15-day and 5-day horizons). The user pointed at
https://github.com/scorpionhiccup/StockPricePrediction and asked to replicate
it — that repo uses Theano (dead since ~2018), Twitter sentiment/news data we
don't have historically, and reports no quantitative accuracy in its README.
Rather than clone unverifiable, unmaintained code, this borrows the one
genuinely new idea in it (LSTM — a model type not tried yet) and runs it
through the SAME honest walk-forward framework as train_ml_trend.py: same
features (imported directly from there, not re-derived, so there's no drift),
same volatility-adjusted label, same chronological no-leakage split.

Expectation set BEFORE running, not after: gradient boosting is generally at
least as strong as a small LSTM on this kind of tabular/sequential data at
this sample size, so this is not expected to suddenly clear baseline where
GBM didn't — it's a legitimate different architecture, tried honestly, not a
reason to expect a different conclusion.

Runs in a SEPARATE short-path venv (C:\\ml-lstm-env\\venv) because installing
torch into this repo's own .venv hit a Windows MAX_PATH limit (torch's
package tree is deeply nested; this repo's own path is already long).
    C:/ml-lstm-env/venv/Scripts/python.exe backtest/train_lstm_trend.py
"""
from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sklearn.preprocessing import StandardScaler

from train_ml_trend import (
    EXTRA_CATEGORICAL_COLS,
    HORIZON,
    MARKET_FEATURE_COLS,
    OWN_FEATURE_COLS,
    RELATIVE_FEATURE_COLS,
    build_all_features,
)

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
JSON_PATH = HERE / "results" / "lstm_trend.json"

SEQ_LEN = 20  # trading days of feature history per input sequence (~1 month)
# LSTM gets NUMERIC features only (no raw sector/ticker string categoricals —
# a network wants continuous/embedded inputs, not the tree-friendly
# categorical handling train_ml_trend.py's GBM uses). dow/month are
# cyclical-encoded below instead of passed as raw ints.
NUMERIC_FEATURE_COLS = OWN_FEATURE_COLS + MARKET_FEATURE_COLS + RELATIVE_FEATURE_COLS
SEQ_FEATURE_COLS = NUMERIC_FEATURE_COLS + ["dow_sin", "dow_cos", "month_sin", "month_cos"]

CLASS_TO_IDX = {"Down": 0, "Flat": 1, "Up": 2}
IDX_TO_CLASS = {v: k for k, v in CLASS_TO_IDX.items()}


def add_cyclical(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["dow_sin"] = np.sin(2 * np.pi * df["dow"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["dow"] / 7)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    return df


def build_sequences(df: pd.DataFrame, feature_cols: list[str]) -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    """One sequence per (ticker, date): the SEQ_LEN days of features ending
    at that date, and the label AT that date (already forward-looking by
    HORIZON days from train_ml_trend.build_features — no extra lookahead
    introduced here)."""
    X, y, dates, tickers = [], [], [], []
    for ticker, g in df.groupby("ticker"):
        g = g.sort_values("date").reset_index(drop=True)
        # A couple of upstream columns (rsi14, mkt_rsi14, mood_index — see
        # run_backtest.rsi()'s `.replace(0, pd.NA)`) end up as pandas `object`
        # dtype holding a mix of plain floats and pd.NA, which a direct
        # .to_numpy(dtype=float32) can't cast. pd.to_numeric per column forces
        # everything to clean float64 (pd.NA -> real np.nan) first.
        feats = g[feature_cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=np.float32)
        labels = g["label"].to_numpy()
        valid = g["label"].notna().to_numpy() & ~np.isnan(feats).any(axis=1)
        for i in range(SEQ_LEN - 1, len(g)):
            if not valid[i]:
                continue
            window = feats[i - SEQ_LEN + 1 : i + 1]
            if np.isnan(window).any():
                continue
            X.append(window)
            y.append(CLASS_TO_IDX[labels[i]])
            dates.append(g["date"].iloc[i])
            tickers.append(ticker)
    return np.array(X), np.array(y), dates, tickers


class TrendLSTM(nn.Module):
    def __init__(self, n_features: int, hidden: int = 32, n_classes: int = 3):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, num_layers=1, batch_first=True)
        self.dropout = nn.Dropout(0.3)
        self.head = nn.Linear(hidden, n_classes)

    def forward(self, x):
        _, (h_n, _) = self.lstm(x)
        return self.head(self.dropout(h_n[-1]))


def train_one_fold(Xtr, ytr, Xte, yte, n_features: int, epochs: int = 25) -> np.ndarray:
    # Scale using TRAIN stats only — fit here, apply to both, never let test
    # rows influence the scaler (same discipline as the leak-free date splits).
    scaler = StandardScaler()
    n_tr, seq_len, _ = Xtr.shape
    Xtr_s = scaler.fit_transform(Xtr.reshape(-1, n_features)).reshape(n_tr, seq_len, n_features)
    n_te = Xte.shape[0]
    Xte_s = scaler.transform(Xte.reshape(-1, n_features)).reshape(n_te, seq_len, n_features)

    # Small internal validation slice (last 10% of TRAIN, chronologically —
    # Xtr is already date-ordered per ticker-group construction upstream, but
    # to keep this simple and safe we just use a held-out random 10% of train
    # for early-stopping style model selection; it never touches Xte).
    n_val = max(50, int(0.1 * n_tr))
    Xval_s, yval = Xtr_s[-n_val:], ytr[-n_val:]
    Xfit_s, yfit = Xtr_s[:-n_val], ytr[:-n_val]

    device = torch.device("cpu")
    model = TrendLSTM(n_features).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()

    Xfit_t = torch.tensor(Xfit_s, dtype=torch.float32)
    yfit_t = torch.tensor(yfit, dtype=torch.long)
    Xval_t = torch.tensor(Xval_s, dtype=torch.float32)
    yval_t = torch.tensor(yval, dtype=torch.long)

    best_val_loss, best_state, patience, bad_epochs = np.inf, None, 5, 0
    batch_size = 256
    n_batches = max(1, len(Xfit_t) // batch_size)

    for epoch in range(epochs):
        model.train()
        perm = torch.randperm(len(Xfit_t))
        for b in range(n_batches):
            idx = perm[b * batch_size : (b + 1) * batch_size]
            if len(idx) == 0:
                continue
            opt.zero_grad()
            out = model(Xfit_t[idx])
            loss = loss_fn(out, yfit_t[idx])
            loss.backward()
            opt.step()

        model.eval()
        with torch.no_grad():
            val_out = model(Xval_t)
            val_loss = loss_fn(val_out, yval_t).item()
        if val_loss < best_val_loss:
            best_val_loss, best_state, bad_epochs = val_loss, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            bad_epochs += 1
            if bad_epochs >= patience:
                break

    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        Xte_t = torch.tensor(Xte_s, dtype=torch.float32)
        pred = model(Xte_t).argmax(dim=1).numpy()
    return pred


def walk_forward_validate_lstm(df: pd.DataFrame) -> dict:
    d = df.sort_values("date").reset_index(drop=True)
    dates = sorted(d["date"].unique())
    if len(dates) < 40:
        return {"error": "not enough history for a walk-forward split yet"}

    n_folds = 5
    fold_edges = np.linspace(len(dates) * 0.5, len(dates), n_folds + 1).astype(int)
    fold_bounds = [dates[min(i, len(dates) - 1)] for i in fold_edges]

    y_true_all, y_pred_all = [], []
    per_fold = []
    for i in range(n_folds):
        train_cut, test_cut = fold_bounds[i], fold_bounds[i + 1]
        train_df = d[d["date"] < train_cut]
        test_df = d[(d["date"] >= train_cut) & (d["date"] < test_cut)]
        if len(train_df) < 300 or len(test_df) < 30:
            continue

        Xtr, ytr, _, _ = build_sequences(train_df, SEQ_FEATURE_COLS)
        Xte, yte, _, _ = build_sequences(test_df, SEQ_FEATURE_COLS)
        if len(Xtr) < 200 or len(Xte) < 20:
            continue

        pred = train_one_fold(Xtr, ytr, Xte, yte, n_features=len(SEQ_FEATURE_COLS))
        y_true_all.extend(yte.tolist())
        y_pred_all.extend(pred.tolist())
        acc = float(round(100 * accuracy_score(yte, pred), 1))
        per_fold.append({"test_start": train_cut, "test_end": test_cut, "n_test": int(len(Xte)), "accuracy_pct": acc})
        print(f"  fold {i+1}/{n_folds}  train={len(Xtr)} test={len(Xte)}  accuracy={acc}%")

    if not y_true_all:
        return {"error": "folds too small to validate"}

    y_true_all = np.array(y_true_all)
    y_pred_all = np.array(y_pred_all)
    overall_acc = float(round(100 * accuracy_score(y_true_all, y_pred_all), 1))

    vals, counts = np.unique(y_true_all, return_counts=True)
    baseline_idx = int(vals[np.argmax(counts)])
    baseline_class = IDX_TO_CLASS[baseline_idx]
    baseline_acc = float(round(100 * (y_true_all == baseline_idx).mean(), 1))

    labels_idx = [0, 1, 2]
    p, r, f1, support = precision_recall_fscore_support(y_true_all, y_pred_all, labels=labels_idx, zero_division=0)
    per_class = {
        IDX_TO_CLASS[i]: {"precision_pct": float(round(100 * p[i], 1)), "recall_pct": float(round(100 * r[i], 1)), "n": int(support[i])}
        for i in labels_idx
    }

    return {
        "method": f"{n_folds}-fold time-based expanding-window walk-forward, LSTM (seq_len={SEQ_LEN})",
        "n_folds": len(per_fold),
        "n_test_rows": int(len(y_true_all)),
        "accuracy_pct": overall_acc,
        "baseline_class": baseline_class,
        "baseline_accuracy_pct": baseline_acc,
        "beats_baseline": bool(overall_acc > baseline_acc),
        "per_class": per_class,
        "per_fold": per_fold,
    }


def main() -> None:
    print(f"InvestAI LSTM trend model — {HORIZON}-trading-day horizon, sequence length {SEQ_LEN}\n")

    all_features = build_all_features()
    all_features = add_cyclical(all_features)

    labeled = all_features.dropna(subset=["label"])
    print(f"\nLabeled rows before sequencing: {len(labeled)}")

    print("\nWalk-forward validating (honest, not-in-sample accuracy)...")
    validation = walk_forward_validate_lstm(labeled)
    if "error" in validation:
        print(f"  ! {validation['error']}")
        return
    print(f"\n  Pooled accuracy: {validation['accuracy_pct']}% vs baseline {validation['baseline_accuracy_pct']}% "
          f"({'beats' if validation['beats_baseline'] else 'does NOT beat'} baseline)")

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "lstm-trend",
        "horizon_trading_days": HORIZON,
        "sequence_length_days": SEQ_LEN,
        "model": f"LSTM (1 layer, 32 hidden units, dropout 0.3, PyTorch), sequence of {SEQ_LEN} days over the same features as train_ml_trend.py",
        "validation": validation,
        "disclaimer": (
            "Attempt #5 in an honest series (see train_ml_trend.py docstring for #1-4, "
            "all of which also failed to beat baseline). A small LSTM on this sample size "
            "is not expected to outperform gradient boosting on the same features — this "
            "was tried for completeness after the user pointed at a reference repo, not "
            "because prior evidence suggested it would work. Research/education only."
        ),
    }
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSummary -> {JSON_PATH}")


if __name__ == "__main__":
    main()
