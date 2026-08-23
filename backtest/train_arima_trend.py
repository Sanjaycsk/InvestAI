"""
InvestAI — ARIMA time-series model for the 15-day trend forecast.

Per-ticker ARIMA on log(close), evaluated with a proper CHRONOLOGICAL
train/test split (80/20, train strictly before test — no leakage) and a
walk-forward test loop (refit periodically through the test period, forecast
15 trading days ahead each time, grade against what actually happened).
Same Up/Down/Flat ±4% bucketing as the gradient-boosting model
(train_ml_trend.py), so the two are directly comparable.

HONESTY NOTE, read before trusting any number this prints: 15-trading-day
directional accuracy for individual equities sits close to a coin flip for
almost every legitimate technique — this is the weak-form efficient-market
hypothesis, and it is why professional quant desks measure edge in basis
points and Sharpe ratio, not "% of days correctly called". If a run of this
script (or any variant of it) reports something like 80%+ test accuracy,
the far more likely explanation is a bug (lookahead leakage, an unrealistic
label threshold that makes one class trivial to always guess, evaluating on
data the model implicitly saw) than a genuinely predictive model — treat a
too-good number as a reason to audit the pipeline, not celebrate it.

Run locally (yfinance needs a non-cloud IP):
    .venv/Scripts/python.exe backtest/train_arima_trend.py
"""
from __future__ import annotations

import itertools
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

from run_backtest import UNIVERSE

HISTORY_PERIOD = "5y"  # run_backtest.fetch_close is hardcoded to 1y — not enough
                        # history for an 80/20 split with a 15-day walk-forward
                        # stride to produce more than a handful of test points.


def fetch_close(symbol: str) -> pd.Series | None:
    import yfinance as yf
    df = yf.download(symbol, period=HISTORY_PERIOD, auto_adjust=True, progress=False)
    if df is None or len(df) == 0:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df["Close"].dropna()

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
JSON_PATH = HERE / "results" / "arima_trend.json"

HORIZON = 15            # trading days ahead — same as the GBM model
UP_THRESH = 0.04
DOWN_THRESH = -0.04
TRAIN_FRAC = 0.8         # chronological 80/20 split, as requested
MIN_HISTORY_ROWS = 150
ORDER_GRID = list(itertools.product([0, 1, 2], [1], [0, 1, 2]))  # d fixed at 1: price series are ~unit-root


def bucket(pct: float) -> str:
    if pct >= UP_THRESH:
        return "Up"
    if pct <= DOWN_THRESH:
        return "Down"
    return "Flat"


def select_order(train_log: pd.Series) -> tuple[int, int, int]:
    """Pick (p,d,q) by AIC on the TRAIN split only — never touches test data."""
    best_order, best_aic = (0, 1, 0), np.inf
    for order in ORDER_GRID:
        try:
            fit = ARIMA(train_log, order=order).fit()
            if fit.aic < best_aic:
                best_aic, best_order = fit.aic, order
        except Exception:
            continue
    return best_order


def forecast_horizon_pct(log_series: pd.Series, order: tuple[int, int, int]) -> tuple[float, float, float] | None:
    """Fit ARIMA on everything up to 'now' and forecast HORIZON steps ahead.
    Returns (point_pct_change, ci_low_pct, ci_high_pct) or None on failure."""
    try:
        fit = ARIMA(log_series, order=order).fit()
        fc = fit.get_forecast(steps=HORIZON)
        point_log = fc.predicted_mean.iloc[-1]
        ci = fc.conf_int(alpha=0.20)  # 80% interval
        lo_log, hi_log = ci.iloc[-1, 0], ci.iloc[-1, 1]
        last_log = log_series.iloc[-1]
        pct = float(np.exp(point_log - last_log) - 1)
        lo_pct = float(np.exp(lo_log - last_log) - 1)
        hi_pct = float(np.exp(hi_log - last_log) - 1)
        return pct, lo_pct, hi_pct
    except Exception:
        return None


def evaluate_ticker(ticker: str, close: pd.Series) -> dict | None:
    if len(close) < MIN_HISTORY_ROWS:
        return None
    log_close = np.log(close)
    n = len(log_close)
    split = int(n * TRAIN_FRAC)
    train_log = log_close.iloc[:split]
    if len(train_log) < 100:
        return None

    order = select_order(train_log)

    # Walk-forward through the TEST portion only, stepping by the horizon
    # (matches how this model would actually be used — retrain periodically,
    # not every single day) and always fitting on data strictly before the
    # forecast origin, never on the future.
    results = []
    t = split
    while t + HORIZON < n:
        history = log_close.iloc[: t + 1]
        fc = forecast_horizon_pct(history, order)
        if fc is not None:
            pred_pct, _, _ = fc
            actual_pct = float(np.exp(log_close.iloc[t + HORIZON] - log_close.iloc[t]) - 1)
            results.append({
                "predicted_class": bucket(pred_pct),
                "actual_class": bucket(actual_pct),
                "predicted_pct": pred_pct,
                "actual_pct": actual_pct,
            })
        t += HORIZON

    if not results:
        return None

    df = pd.DataFrame(results)
    n_correct = int((df.predicted_class == df.actual_class).sum())
    baseline_class = df["actual_class"].mode().iloc[0]
    n_baseline_correct = int((df["actual_class"] == baseline_class).sum())

    # Today's live forecast: fit on the FULL series (train+test), forecast forward.
    live = forecast_horizon_pct(log_close, order)

    return {
        "ticker": ticker,
        "order": order,
        "n_test_forecasts": len(df),
        "n_correct": n_correct,
        "accuracy_pct": round(100 * n_correct / len(df), 1),
        "baseline_class": baseline_class,
        "baseline_accuracy_pct": round(100 * n_baseline_correct / len(df), 1),
        "live_forecast": (
            {
                "predicted_pct": round(100 * live[0], 2),
                "ci_low_pct": round(100 * live[1], 2),
                "ci_high_pct": round(100 * live[2], 2),
                "predicted_class": bucket(live[0]),
            }
            if live is not None
            else None
        ),
        "test_rows": results,
    }


def main() -> None:
    print(f"InvestAI ARIMA trend model — {HORIZON}-trading-day horizon, {TRAIN_FRAC:.0%}/{1 - TRAIN_FRAC:.0%} train/test split\n")

    per_ticker = []
    for t in UNIVERSE:
        close = fetch_close(f"{t}.NS")
        if close is None:
            print(f"  ! {t}: no data, skipping")
            continue
        res = evaluate_ticker(t, close)
        if res is None:
            print(f"  ! {t}: insufficient history for a clean 80/20 split, skipping")
            continue
        per_ticker.append(res)
        print(f"  ok {t}: order={res['order']}  test accuracy {res['accuracy_pct']}% "
              f"(baseline {res['baseline_accuracy_pct']}%)  n={res['n_test_forecasts']}")

    if not per_ticker:
        print("No tickers produced a valid evaluation — aborting.")
        return

    total_correct = sum(r["n_correct"] for r in per_ticker)
    total_n = sum(r["n_test_forecasts"] for r in per_ticker)
    pooled_acc = round(100 * total_correct / total_n, 1)

    # Pooled baseline: majority class over ALL test rows across all tickers
    # (a per-ticker mode can differ from the pooled mode; this is the fair
    # apples-to-apples comparison).
    all_actuals = [row["actual_class"] for r in per_ticker for row in r["test_rows"]]
    pooled_baseline_class = pd.Series(all_actuals).mode().iloc[0]
    pooled_baseline_acc = round(100 * (pd.Series(all_actuals) == pooled_baseline_class).mean(), 1)

    predictions = [
        {
            "ticker": r["ticker"],
            "order": list(r["order"]),
            "predicted_class": r["live_forecast"]["predicted_class"] if r["live_forecast"] else None,
            "predicted_pct": r["live_forecast"]["predicted_pct"] if r["live_forecast"] else None,
            "ci_low_pct": r["live_forecast"]["ci_low_pct"] if r["live_forecast"] else None,
            "ci_high_pct": r["live_forecast"]["ci_high_pct"] if r["live_forecast"] else None,
            "test_accuracy_pct": r["accuracy_pct"],
            "test_n": r["n_test_forecasts"],
        }
        for r in per_ticker
        if r["live_forecast"] is not None
    ]

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "arima-trend-15d",
        "horizon_trading_days": HORIZON,
        "model": "Per-ticker ARIMA on log(close), order chosen by AIC on the train split",
        "split": {"train_frac": TRAIN_FRAC, "method": "chronological (train strictly before test)"},
        "label_thresholds": {"up_pct": UP_THRESH * 100, "down_pct": DOWN_THRESH * 100},
        "validation": {
            "method": "walk-forward over the held-out 20% test period, refit every 15 trading days, forecast 15 days ahead each time",
            "n_tickers": len(per_ticker),
            "n_test_forecasts": total_n,
            "accuracy_pct": pooled_acc,
            "baseline_class": str(pooled_baseline_class),
            "baseline_accuracy_pct": pooled_baseline_acc,
            "beats_baseline": bool(pooled_acc > pooled_baseline_acc),
        },
        "per_ticker": [
            {"ticker": r["ticker"], "order": list(r["order"]), "accuracy_pct": r["accuracy_pct"],
             "baseline_accuracy_pct": r["baseline_accuracy_pct"], "n": r["n_test_forecasts"]}
            for r in per_ticker
        ],
        "predictions": predictions,
        "disclaimer": (
            "Per-ticker ARIMA on price alone (no technical/fundamental features), evaluated "
            "on a genuine held-out 20% chronological test split — this number has NOT been "
            "tuned against the test set. 15-trading-day directional forecasting for individual "
            "equities is close to a coin flip for almost any legitimate model (weak-form "
            "market efficiency); treat any very high accuracy figure as a reason to check for "
            "a leak, not as a validated edge. Research/education only, never a price target."
        ),
    }

    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== RESULT ===")
    print(f"Pooled test accuracy : {pooled_acc}%  (n={total_n})")
    print(f"Pooled baseline      : {pooled_baseline_acc}% (always guess '{pooled_baseline_class}')")
    print(f"Beats baseline       : {summary['validation']['beats_baseline']}")
    print(f"\nSummary -> {JSON_PATH}")


if __name__ == "__main__":
    main()
