"""
InvestAI — short-horizon (HORIZON trading days) ML trend model (traditional
ML, NOT the LLM agent).

A second, independent opinion alongside the daily LLM verdict: for each of
the 26 instruments, a gradient-boosted classifier predicts whether the close
HORIZON trading days from now will be meaningfully Up, meaningfully Down, or
roughly Flat (volatility-adjusted per ticker) — a directional lean +
confidence, never a price target. Features span own technicals (incl.
open-gap, ATR/true-range, day-of-week/month seasonality), cross-asset macro
(Nifty/US markets/USD-INR/crude oil/India VIX, all 1-day-lagged), sector
cohesion (relative strength, sector-average momentum, sector breadth), and a
price-data-only 0-100 "mood index" proxying the dashboard's own sentiment
gauge. Went through two failed attempts at HORIZON=15 (plain GBM, then
ARIMA) before this richer version — see backtest/train_arima_trend.py and
the conversation history for the honest failures that led here.

Storage tiers (same design as run_backtest.py):
  - HEAVY: local SQLite `backtest.db` — feature table + a running prediction
    history (gitignored, stays on the PC).
  - TINY: `backtest/results/ml_trend.json` — today's predictions + honest
    validation stats. NOT bundled with the dashboard: the walk-forward numbers
    never beat a naive baseline, so nothing here is rendered in the UI (see
    AGENT.md 2026-08-12). Kept as a research record.

Self-grading loop: every run first grades any of ITS OWN past predictions
whose target date has now arrived (Correct/Wrong, same idea as the live
agent's Step 1), so a real live track record accumulates over time —
separate from the walk-forward backtest accuracy, which is an in-sample-free
but not-yet-live estimate.

Run locally (yfinance works on a home IP; it is blocked in the Anthropic
cloud sandbox that runs the live agent):
    .venv/Scripts/python.exe backtest/train_ml_trend.py

Re-run periodically and redeploy the dashboard to pick up fresh predictions.
"""
from __future__ import annotations

import json
import sqlite3
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

from run_backtest import EQUITIES, ETFS, UNIVERSE, rsi

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "backtest.db"
JSON_PATH = HERE / "results" / "ml_trend.json"

HORIZON = 5             # trading days ahead — shortened from 15 after two honest
                        # attempts (GBM, ARIMA) failed to beat baseline at 15d;
                        # shorter horizons carry more real momentum/mean-reversion
                        # signal in the literature, worth an honest try.
MIN_HISTORY_ROWS = 80   # below this, a ticker's features are too thin to trust
# ^NSEI (real Nifty 50 index), NOT GROWWN200 — GROWWN200 is one of the 26
# tradable instruments but only has ~1.5y of listed history, which would
# truncate every OTHER ticker's usable training data down to that same short
# window if used as the regime source. ^NSEI has the full lookback.
MARKET_INDEX_SYMBOL = "^NSEI"

# Labels are VOLATILITY-ADJUSTED, not a flat +/-4% for every name: a stock
# that routinely moves 8% in 15 days and one that routinely moves 2% don't
# mean the same thing by "Flat" under one fixed bar — normalising by each
# ticker's own trailing volatility makes the three classes mean the same
# RELATIVE thing for every instrument, which is a more honest target than an
# arbitrary absolute cutoff (this is a modeling/labeling design choice, fixed
# once up front — never tuned against the walk-forward accuracy it produces).
VOL_MULT = 0.5  # "Up"/"Down" = forward return beyond 0.5x the 15-day-scaled trailing vol

# Mirrors dashboard/lib/sectors.ts — kept in sync by hand (small, stable
# watchlist; not worth a cross-language shared source of truth yet).
SECTOR = {
    "HDFCBANK": "banking", "ICICIBANK": "banking", "SBIN": "banking", "FEDERALBNK": "banking",
    "TCS": "it", "INFY": "it",
    "ITC": "fmcg", "HINDUNILVR": "fmcg",
    "MARUTI": "auto",
    "SUNPHARMA": "pharma",
    "TATASTEEL": "metals", "VEDL": "metals",
    "RELIANCE": "energy", "BPCL": "energy", "ADANIENT": "energy",
    "NTPC": "power", "TATAPOWER": "power",
    "LT": "industrials", "BHEL": "industrials",
    "SUZLON": "renewables", "WAAREEENER": "renewables",
    "BEL": "defense",
    "BHARTIARTL": "telecom",
    "GROWWN200": "broad-market",
    "GOLDBEES": "commodities", "SILVERBEES": "commodities",
}

OWN_FEATURE_COLS = [
    "ret_5d", "ret_10d", "ret_20d", "ret_60d",
    "rsi14",
    "vs_dma20", "vs_dma50", "vs_dma200",
    "macd_hist",
    "vol_20d", "vol_60d",
    "vol_chg_20d",
    "dist_52w_high", "dist_52w_low",
    "open_gap",       # today's open vs yesterday's close — overnight move
    "atr_pct",        # true-range volatility (uses High/Low, not just Close) as % of price
    "atr_chg_20d",    # is the trading range EXPANDING or CONTRACTING lately
]
SEASONALITY_FEATURE_COLS = ["dow", "month"]  # day-of-week, month — small-sample but free
# Broad-market regime, the SAME for every ticker on a given date — lets the
# model condition its per-stock read on whether the whole market is trending
# up/down/choppy that day, a systematic factor individual-name technicals
# can't see on their own.
MARKET_FEATURE_COLS = [
    "mkt_ret_20d", "mkt_vs_dma50", "mkt_vs_dma200", "mkt_rsi14",
    "us_sp500_ret1d", "us_nasdaq_ret1d",   # prior US session, lagged 1 day (no same-day leak)
    "usdinr_ret1d", "crude_oil_ret1d",
    "india_vix_level", "india_vix_ret1d",
    "mood_index",     # 0-100 price-data-only fear/greed proxy, see build_mood_index()
]
# Cross-sectional: is this name outperforming or lagging its OWN sector's
# average momentum right now, AND is the sector as a whole moving together
# (sector comovement — e.g. one defense name selling off tends to drag the
# others with it within a few days).
RELATIVE_FEATURE_COLS = ["rel_strength_20d", "sector_ret_5d", "sector_breadth"]

FEATURE_COLS = (
    OWN_FEATURE_COLS + SEASONALITY_FEATURE_COLS + MARKET_FEATURE_COLS + RELATIVE_FEATURE_COLS
    + ["sector", "ticker"]
)
# dow/month behave as categoricals (Monday isn't "less than" Friday) even
# though they're stored as small ints.
EXTRA_CATEGORICAL_COLS = ["dow", "month"]


def classify(fwd_ret: float, vol_60d: float) -> str:
    """Same volatility-adjusted bucketing rule used for training labels,
    reused for grading past predictions so the two are always consistent."""
    if pd.isna(fwd_ret) or pd.isna(vol_60d):
        return "Flat"
    expected_vol_horizon = vol_60d * np.sqrt(HORIZON)
    bar = VOL_MULT * expected_vol_horizon
    if fwd_ret >= bar:
        return "Up"
    if fwd_ret <= -bar:
        return "Down"
    return "Flat"


def fetch_close_5y(symbol: str) -> pd.Series | None:
    """5-year single-series fetch — NOT run_backtest.fetch_close, which is
    hardcoded to a 1-year window (fine for that script's purpose, not this
    one's)."""
    import yfinance as yf
    df = yf.download(symbol, period="5y", auto_adjust=True, progress=False)
    if df is None or len(df) == 0:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df["Close"].dropna()


def build_market_regime() -> pd.DataFrame:
    """Nifty 50 index's own technical state per date — broadcast onto every
    ticker's row later so the model can see whether the WHOLE market is
    trending, not just one name in isolation."""
    close = fetch_close_5y(MARKET_INDEX_SYMBOL)
    if close is None:
        return pd.DataFrame(columns=["date", "mkt_ret_20d", "mkt_vs_dma50", "mkt_vs_dma200", "mkt_rsi14"])
    dma50 = close.rolling(50).mean()
    dma200 = close.rolling(200).mean()
    m = pd.DataFrame({
        "mkt_ret_20d": close.pct_change(20),
        "mkt_vs_dma50": close / dma50 - 1,
        "mkt_vs_dma200": close / dma200 - 1,
        "mkt_rsi14": rsi(close, 14),
    })
    m = m.reset_index().rename(columns={"Date": "date", "index": "date"})
    m["date"] = pd.to_datetime(m["date"]).dt.strftime("%Y-%m-%d")
    return m


# yfinance symbol -> our column prefix.
MACRO_SYMBOLS = {
    "^GSPC": "us_sp500",
    "^IXIC": "us_nasdaq",
    "INR=X": "usdinr",
    "CL=F": "crude_oil",
    "^INDIAVIX": "india_vix",
}


def build_macro_features() -> pd.DataFrame:
    """Cross-asset context: US markets, USD/INR, crude oil, India VIX — all
    free via yfinance, all confirmed to have ~5y of history. Lagged by 1
    calendar day across the board (conservative — avoids any same-day
    cross-timezone leakage) and matched onto India trading dates with
    merge_asof (backward), so a US/global holiday that doesn't line up with
    an NSE holiday still gets the most recent PRIOR reading, not a gap."""
    cols = []
    frames = []
    for sym, prefix in MACRO_SYMBOLS.items():
        close = fetch_close_5y(sym)
        if close is None:
            print(f"  ! macro {sym}: no data, skipping")
            continue
        s = pd.DataFrame(index=pd.to_datetime(close.index))
        s[f"{prefix}_ret1d"] = close.pct_change().values
        cols.append(f"{prefix}_ret1d")
        if prefix == "india_vix":
            s["india_vix_level"] = close.values
            cols.append("india_vix_level")
        frames.append(s)

    if not frames:
        return pd.DataFrame(columns=["date"] + cols)

    macro = pd.concat(frames, axis=1)
    macro.index.name = "date"
    macro = macro.reset_index()
    # Lag 1 day: nothing is usable on the same calendar date it happened.
    macro["date"] = macro["date"] + pd.Timedelta(days=1)
    return macro.sort_values("date")


def build_mood_index(all_dates: pd.Series, all_features: pd.DataFrame, macro: pd.DataFrame) -> pd.DataFrame:
    """A price-data-only 0(panic)-100(everyone's greedy) daily proxy for the
    live dashboard's own sentiment gauge (dashboard/lib/notion.ts
    computeSentiment) — NOT the same thing, since that one reads the LLM
    agent's actual daily verdicts, which only exist for ~45 days, nowhere
    near enough to train on. This reconstructs an analogous signal from 5
    years of price data alone: cross-sectional breadth (% of the universe
    above its own 50-DMA), average RSI, Nifty's own momentum, and India VIX
    (inverted, percentile-ranked against its own trailing year so it adapts
    to the current volatility regime rather than a fixed hard-coded band)."""
    # Everything below stays indexed by the "YYYY-MM-DD" STRING date on
    # purpose (not converted to datetime) — lexicographic order on that
    # format is already chronological, .rolling() only cares about row
    # order, and keeping one consistent index type avoids a datetime/string
    # reindex mismatch silently reindexing everything to NaN.
    by_date = all_features.groupby("date")
    breadth = by_date["vs_dma50"].apply(lambda s: 100 * (s > 0).mean())
    avg_rsi = by_date["rsi14"].mean()  # already 0-100

    mkt = (
        all_features[["date", "mkt_ret_20d"]]
        .drop_duplicates("date")
        .set_index("date")["mkt_ret_20d"]
        .sort_index()
    )
    mom_component = (mkt.clip(-0.15, 0.15) + 0.15) / 0.30 * 100  # -15%..+15% -> 0..100

    if "india_vix_level" in macro.columns:
        vix = macro.drop_duplicates("date").set_index("date")["india_vix_level"].sort_index()
        vix_pct_rank = vix.rolling(252, min_periods=60).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1])
        vix_component = (1 - vix_pct_rank) * 100  # high VIX (vs its own trailing year) -> low mood
    else:
        vix_component = pd.Series(dtype=float)

    dates_sorted = sorted(all_dates.unique())
    idx = pd.DataFrame(index=dates_sorted)
    idx["breadth"] = breadth.reindex(dates_sorted)
    idx["avg_rsi"] = avg_rsi.reindex(dates_sorted)
    idx["mom"] = mom_component.reindex(dates_sorted)
    idx["vix"] = vix_component.reindex(dates_sorted)

    idx["mood_index"] = idx[["breadth", "avg_rsi", "mom", "vix"]].mean(axis=1, skipna=True)
    idx = idx.reset_index().rename(columns={"index": "date"})
    return idx[["date", "mood_index"]]


def fetch_ohlcv(symbol: str) -> pd.DataFrame | None:
    df = yf_download_full(symbol)
    if df is None or len(df) == 0:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


def yf_download_full(symbol: str) -> pd.DataFrame | None:
    import yfinance as yf
    df = yf.download(symbol, period="5y", auto_adjust=True, progress=False)
    return df


def build_features(ticker: str, ohlcv: pd.DataFrame) -> pd.DataFrame:
    close = ohlcv["Close"]
    open_ = ohlcv["Open"]
    high = ohlcv["High"]
    low = ohlcv["Low"]
    vol = ohlcv["Volume"]
    df = pd.DataFrame({"close": close, "open": open_, "volume": vol})

    # Overnight gap: today's open vs YESTERDAY's close.
    df["open_gap"] = open_ / close.shift(1) - 1

    # True Range / ATR — uses High and Low, not just Close, so it captures
    # INTRADAY range, not just close-to-close volatility (vol_20d/vol_60d
    # below only see the closing prints). "Is the day-to-day high-low swing
    # widening or narrowing lately" per the volatility-breakout idea.
    prev_close = close.shift(1)
    true_range = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr14 = true_range.rolling(14).mean()
    df["atr_pct"] = atr14 / close
    df["atr_chg_20d"] = atr14 / atr14.shift(20) - 1

    # Seasonality — cheap to add with 5y of history, day-of-week has ~1,250
    # samples; month is thinner (~5 per calendar month) but still free.
    dt_index = pd.to_datetime(close.index)
    df["dow"] = dt_index.dayofweek
    df["month"] = dt_index.month

    df["ret_5d"] = close.pct_change(5)
    df["ret_10d"] = close.pct_change(10)
    df["ret_20d"] = close.pct_change(20)
    df["ret_60d"] = close.pct_change(60)

    df["rsi14"] = rsi(close, 14)

    dma20 = close.rolling(20).mean()
    dma50 = close.rolling(50).mean()
    dma200 = close.rolling(200).mean()
    df["vs_dma20"] = close / dma20 - 1
    df["vs_dma50"] = close / dma50 - 1
    df["vs_dma200"] = close / dma200 - 1

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    df["macd_hist"] = macd - macd_signal

    daily_ret = close.pct_change()
    df["vol_20d"] = daily_ret.rolling(20).std()
    df["vol_60d"] = daily_ret.rolling(60).std()

    vol_mean_20d = vol.rolling(20).mean()
    df["vol_chg_20d"] = vol / vol_mean_20d - 1

    roll_high_252 = close.rolling(252, min_periods=20).max()
    roll_low_252 = close.rolling(252, min_periods=20).min()
    df["dist_52w_high"] = close / roll_high_252 - 1
    df["dist_52w_low"] = close / roll_low_252 - 1

    # Forward label — what we're trying to predict. Volatility-adjusted (see
    # VOL_MULT comment above): the bar for "Up"/"Down" scales with how much
    # this specific name typically moves, using trailing (not forward) vol so
    # there's no lookahead in the threshold itself.
    fwd_ret = close.shift(-HORIZON) / close - 1
    df["fwd_ret"] = fwd_ret
    expected_vol_horizon = df["vol_60d"] * np.sqrt(HORIZON)
    up_bar = VOL_MULT * expected_vol_horizon
    down_bar = -VOL_MULT * expected_vol_horizon
    df["label"] = np.select(
        [fwd_ret >= up_bar, fwd_ret <= down_bar],
        ["Up", "Down"],
        default="Flat",
    )
    df.loc[fwd_ret.isna() | expected_vol_horizon.isna(), "label"] = None  # unknown future/vol -> unlabeled

    df["ticker"] = ticker
    df["sector"] = SECTOR.get(ticker, "other")
    df = df.reset_index().rename(columns={"Date": "date", "index": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df


def walk_forward_validate(labeled: pd.DataFrame) -> dict:
    """Time-based expanding-window validation: each fold trains on everything
    before a cutoff date and tests on the following slice, so no fold ever
    trains on data from its own future. Folds are pooled-dataset date slices
    (all tickers together), a pragmatic approximation — not a per-ticker
    leak-free split, but standard practice for this data size and enough to
    give an honest, not-in-sample accuracy read."""
    d = labeled.sort_values("date").reset_index(drop=True)
    dates = sorted(d["date"].unique())
    if len(dates) < 40:
        return {"error": "not enough history for a walk-forward split yet"}

    n_folds = 5
    fold_edges = np.linspace(len(dates) * 0.5, len(dates), n_folds + 1).astype(int)
    fold_bounds = [dates[min(i, len(dates) - 1)] for i in fold_edges]

    cat_cols = ["sector", "ticker"] + EXTRA_CATEGORICAL_COLS
    X_cols = [c for c in FEATURE_COLS if c not in cat_cols]
    all_cols = X_cols + cat_cols

    y_true_all, y_pred_all = [], []
    per_fold = []
    for i in range(n_folds):
        train_cut, test_cut = fold_bounds[i], fold_bounds[i + 1]
        train = d[d["date"] < train_cut]
        test = d[(d["date"] >= train_cut) & (d["date"] < test_cut)]
        if len(train) < 200 or len(test) < 20:
            continue

        Xtr, ytr = _prep(train, all_cols, cat_cols)
        Xte, yte = _prep(test, all_cols, cat_cols)

        clf = HistGradientBoostingClassifier(
            max_iter=150, categorical_features=[c in cat_cols for c in all_cols],
            random_state=42,
        )
        clf.fit(Xtr, ytr)
        pred = clf.predict(Xte)

        y_true_all.extend(yte.tolist())
        y_pred_all.extend(pred.tolist())
        per_fold.append({
            "test_start": train_cut, "test_end": test_cut,
            "n_test": int(len(test)), "accuracy_pct": _f(round(100 * accuracy_score(yte, pred), 1)),
        })

    if not y_true_all:
        return {"error": "folds too small to validate"}

    y_true_all = pd.Series(y_true_all)
    y_pred_all = pd.Series(y_pred_all)
    overall_acc = _f(round(100 * accuracy_score(y_true_all, y_pred_all), 1))

    # Baseline: always predict the most common class in the training data —
    # the bar this model actually has to clear to be worth looking at.
    baseline_class = str(y_true_all.mode().iloc[0])
    baseline_acc = _f(round(100 * (y_true_all == baseline_class).mean(), 1))

    labels = ["Up", "Flat", "Down"]
    p, r, f1, support = precision_recall_fscore_support(
        y_true_all, y_pred_all, labels=labels, zero_division=0
    )
    per_class = {
        lbl: {
            "precision_pct": _f(round(100 * p[i], 1)),
            "recall_pct": _f(round(100 * r[i], 1)),
            "n": int(support[i]),
        }
        for i, lbl in enumerate(labels)
    }

    return {
        "method": f"{n_folds}-fold time-based expanding-window walk-forward",
        "n_folds": len(per_fold),
        "n_test_rows": int(len(y_true_all)),
        "accuracy_pct": overall_acc,
        "baseline_class": baseline_class,
        "baseline_accuracy_pct": baseline_acc,
        "beats_baseline": bool(overall_acc > baseline_acc),
        "per_class": per_class,
        "per_fold": per_fold,
    }


def _f(x) -> float:
    """numpy float64/float32 -> plain Python float, so json.dumps doesn't choke."""
    return float(x)


def _prep(df: pd.DataFrame, all_cols: list[str], cat_cols: list[str]):
    X = df[all_cols].copy()
    for c in cat_cols:
        X[c] = X[c].astype("category")
    y = df["label"]
    return X, y


def grade_past_predictions(con: sqlite3.Connection, all_features: pd.DataFrame) -> int:
    """Self-grading: any previously-logged prediction whose target date has
    now arrived gets graded Correct/Wrong from the price data we just
    fetched, exactly the way the live agent grades its own 1-day calls."""
    try:
        hist = pd.read_sql("SELECT * FROM ml_predictions_history", con)
    except Exception:
        return 0
    pending = hist[hist["outcome"] == "Pending"]
    if pending.empty:
        return 0

    graded = 0
    by_ticker = {
        t: sub.set_index("date")[["close", "vol_60d"]] for t, sub in all_features.groupby("ticker")
    }
    for idx, row in pending.iterrows():
        tbl = by_ticker.get(row["ticker"])
        if tbl is None or row["target_date"] not in tbl.index or row["as_of_date"] not in tbl.index:
            continue
        base = tbl.loc[row["as_of_date"], "close"]
        target = tbl.loc[row["target_date"], "close"]
        vol_60d_then = tbl.loc[row["as_of_date"], "vol_60d"]
        actual_ret = target / base - 1
        actual_class = classify(actual_ret, vol_60d_then)
        outcome = "Correct" if actual_class == row["predicted_class"] else "Wrong"
        con.execute(
            "UPDATE ml_predictions_history SET outcome=?, actual_ret_pct=? WHERE ticker=? AND as_of_date=?",
            (outcome, round(100 * actual_ret, 2), row["ticker"], row["as_of_date"]),
        )
        graded += 1
    con.commit()
    return graded


def build_all_features() -> pd.DataFrame:
    """Fetch + engineer the full pooled feature table (own technicals +
    market regime + macro + sector cohesion + mood index) for all 26
    instruments. Pulled out of main() so other scripts (e.g.
    train_lstm_trend.py) can reuse the EXACT same pipeline instead of a
    hand-copied, driftable duplicate."""
    frames = []
    for t in UNIVERSE:
        ohlcv = fetch_ohlcv(f"{t}.NS")
        if ohlcv is None or len(ohlcv) < MIN_HISTORY_ROWS:
            print(f"  ! {t}: insufficient history, skipping")
            continue
        frames.append(build_features(t, ohlcv))
        print(f"  ok {t}: {len(ohlcv)} days")

    all_features = pd.concat(frames, ignore_index=True)

    # ---- market regime: broadcast the Nifty 50 index's own technical state
    # onto every ticker's row for that date, so the model can condition on
    # "is the whole market trending" rather than judging each name in
    # isolation ----
    print(f"\nFetching market regime ({MARKET_INDEX_SYMBOL})...")
    mkt = build_market_regime()
    all_features = all_features.merge(mkt, on="date", how="left")

    # ---- cross-asset macro: US markets / USD-INR / crude / India VIX,
    # merge_asof so cross-market holiday mismatches don't create gaps ----
    print("Fetching macro/cross-asset features (US markets, USD/INR, crude, India VIX)...")
    macro = build_macro_features()
    all_features["date"] = pd.to_datetime(all_features["date"])
    all_features = all_features.sort_values("date")
    all_features = pd.merge_asof(all_features, macro.sort_values("date"), on="date", direction="backward")
    all_features["date"] = all_features["date"].dt.strftime("%Y-%m-%d")
    macro["date"] = macro["date"].dt.strftime("%Y-%m-%d")  # for build_mood_index below

    # ---- sector cohesion: this name's 20d momentum relative to its sector's
    # average (rel_strength_20d), how the sector as a WHOLE has moved lately
    # (sector_ret_5d), and what fraction of the sector is technically healthy
    # right now (sector_breadth) — "if one defense name is down, are the
    # others also down" as an actual feature, not just an anecdote ----
    g = all_features.groupby(["date", "sector"])
    all_features["rel_strength_20d"] = all_features["ret_20d"] - g["ret_20d"].transform("mean")
    all_features["sector_ret_5d"] = g["ret_5d"].transform("mean")
    all_features["sector_breadth"] = g["vs_dma50"].transform(lambda s: 100 * (s > 0).mean())

    # ---- daily mood index (0=panic, 100=greedy), price-data-only proxy ----
    print("Building daily mood index...")
    mood = build_mood_index(all_features["date"], all_features, macro)
    all_features = all_features.merge(mood, on="date", how="left")
    return all_features


def main() -> None:
    print(f"InvestAI ML trend model — {HORIZON}-trading-day horizon, {len(UNIVERSE)} instruments\n")

    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS ml_predictions_history (
            ticker TEXT, as_of_date TEXT, target_date TEXT,
            predicted_class TEXT, confidence_pct REAL,
            actual_ret_pct REAL, outcome TEXT,
            PRIMARY KEY (ticker, as_of_date)
        )"""
    )
    con.commit()

    all_features = build_all_features()

    con.execute("DROP TABLE IF EXISTS ml_features")
    all_features.to_sql("ml_features", con, if_exists="replace", index=False)

    n_graded = grade_past_predictions(con, all_features)
    print(f"\nGraded {n_graded} past prediction(s) whose {HORIZON}-day target date has arrived.")

    _numeric_feature_cols = [c for c in FEATURE_COLS if c not in ("sector", "ticker") + tuple(EXTRA_CATEGORICAL_COLS)]
    labeled = all_features.dropna(subset=["label"] + _numeric_feature_cols, how="any")
    labeled = labeled.dropna(subset=["label"])
    print(f"Training rows (labeled, pooled across tickers): {len(labeled)}")

    print("\nWalk-forward validating (honest, not-in-sample accuracy)...")
    validation = walk_forward_validate(labeled)
    if "error" in validation:
        print(f"  ! {validation['error']}")
    else:
        print(f"  Accuracy: {validation['accuracy_pct']}% vs baseline {validation['baseline_accuracy_pct']}% "
              f"({'beats' if validation['beats_baseline'] else 'does NOT beat'} baseline)")

    # ---- final production model: train on ALL available labeled history ----
    cat_cols = ["sector", "ticker"] + EXTRA_CATEGORICAL_COLS
    X_cols = [c for c in FEATURE_COLS if c not in cat_cols]
    all_cols = X_cols + cat_cols
    Xall, yall = _prep(labeled, all_cols, cat_cols)
    prod_model = HistGradientBoostingClassifier(
        max_iter=150, categorical_features=[c in cat_cols for c in all_cols],
        random_state=42,
    )
    prod_model.fit(Xall, yall)

    import joblib
    joblib.dump(prod_model, HERE / "ml_trend_model.joblib")

    # ---- today's prediction per ticker: latest row with complete features ----
    latest = (
        all_features.sort_values("date")
        .groupby("ticker", as_index=False)
        .tail(1)
    )
    latest = latest.dropna(subset=X_cols, how="any")

    predictions = []
    trading_dates = sorted(all_features["date"].unique())
    for _, row in latest.iterrows():
        Xrow = row[all_cols].to_frame().T
        for c in cat_cols:
            Xrow[c] = Xrow[c].astype("category")
        proba = prod_model.predict_proba(Xrow)[0]
        classes = list(prod_model.classes_)
        probs = {cls: _f(round(100 * p, 1)) for cls, p in zip(classes, proba)}
        pred_class = classes[int(np.argmax(proba))]
        confidence = probs[pred_class]

        as_of_date = row["date"]
        idx = trading_dates.index(as_of_date) if as_of_date in trading_dates else None
        target_date = trading_dates[idx + HORIZON] if idx is not None and idx + HORIZON < len(trading_dates) else None

        predictions.append({
            "ticker": row["ticker"],
            "sector": row["sector"],
            "as_of_date": as_of_date,
            "predicted_class": pred_class,
            "confidence_pct": confidence,
            "class_probs": probs,
        })

        if target_date:
            con.execute(
                """INSERT OR IGNORE INTO ml_predictions_history
                   (ticker, as_of_date, target_date, predicted_class, confidence_pct, outcome)
                   VALUES (?, ?, ?, ?, ?, 'Pending')""",
                (row["ticker"], as_of_date, target_date, pred_class, confidence),
            )
    con.commit()

    # ---- live track record (from ACTUAL graded past predictions, not backtest) ----
    graded_hist = pd.read_sql(
        "SELECT * FROM ml_predictions_history WHERE outcome IN ('Correct','Wrong')", con
    )
    live_track_record = None
    if len(graded_hist) >= 5:
        live_track_record = {
            "n_graded": int(len(graded_hist)),
            "accuracy_pct": _f(round(100 * (graded_hist["outcome"] == "Correct").mean(), 1)),
        }

    con.close()

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "ml-trend",
        "horizon_trading_days": HORIZON,
        "model": (
            "HistGradientBoostingClassifier (scikit-learn), pooled across all instruments; "
            "features = own technicals (incl. open-gap, ATR, seasonality) + Nifty/US/USDINR/"
            "crude/VIX macro regime + sector-relative strength + price-data-only mood index"
        ),
        "label_thresholds": {"method": "volatility-adjusted", "vol_multiplier": VOL_MULT},
        "validation": validation,
        "live_track_record": live_track_record,
        "predictions": sorted(predictions, key=lambda p: p["ticker"]),
        "disclaimer": (
            "A traditional ML model (gradient boosting on price/technical/macro features), "
            "SEPARATE from the daily LLM agent above — a second opinion, not a replacement. "
            f"This predicts a DIRECTIONAL LEAN over {HORIZON} trading days, never a price "
            "target; short-horizon equity forecasting is inherently noisy. 'Validation' is "
            "an honest not-in-sample backtest; 'live track record' (once it exists) is this "
            "model's actual graded predictions over time. Research/education only."
        ),
    }
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== RESULT ===")
    print(f"Predictions for {len(predictions)} instruments written.")
    if live_track_record:
        print(f"Live track record: {live_track_record['accuracy_pct']}% over {live_track_record['n_graded']} graded calls")
    else:
        print("Live track record: not enough graded predictions yet (need 15 trading days + 5 graded calls)")
    print(f"\nModel + heavy tables -> {DB_PATH} / {HERE / 'ml_trend_model.joblib'}")
    print(f"Summary              -> {JSON_PATH}")


if __name__ == "__main__":
    main()
