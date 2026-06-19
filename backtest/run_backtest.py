"""
InvestAI — one-shot historical backtest (technical baseline).

This is NOT a replay of the live Claude agent (that would be cost-prohibitive and
risk look-ahead bias on fundamentals). It is an honest, deterministic
trend+momentum strategy over the same 24-instrument universe, graded with the
SAME thresholds the live agent uses, and benchmarked against simply holding
NIFTY 50. It answers the question that actually matters: "would systematically
trading these names have beaten buy-and-hold?"

Storage tiers (by design):
  - HEAVY base tables  -> local SQLite (backtest.db), gitignored, stays on the PC.
  - TINY summary       -> dashboard/data/backtest.json, bundled with the dashboard.

Run locally (yfinance works on a home IP; it is blocked in the Anthropic cloud):
    .venv/Scripts/python.exe backtest/run_backtest.py
"""
from __future__ import annotations

import json
import sqlite3
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

EQUITIES = [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "TCS", "INFY", "BHARTIARTL", "ITC",
    "HINDUNILVR", "LT", "MARUTI", "SUNPHARMA", "TATASTEEL", "SBIN", "FEDERALBNK",
    "SUZLON", "TATAPOWER", "WAAREEENER", "NTPC", "ADANIENT", "BEL", "BHEL",
]
ETFS = ["GROWWN200", "GOLDBEES", "SILVERBEES"]
UNIVERSE = EQUITIES + ETFS
BENCHMARK = "^NSEI"  # NIFTY 50

PERIOD = "1y"
HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "backtest.db"
JSON_PATH = HERE.parent / "dashboard" / "data" / "backtest.json"

# Grading thresholds — identical to the live agent's Step 1.
BUY_HIT = 0.003      # BUY correct if next-day return > +0.3%
SELL_HIT = -0.003    # SELL correct if next-day return < -0.3%
HOLD_BAND = 0.015    # HOLD correct if |next-day return| <= 1.5%


def fetch_close(symbol: str) -> pd.Series | None:
    df = yf.download(symbol, period=PERIOD, auto_adjust=True, progress=False)
    if df is None or len(df) == 0:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df["Close"].dropna()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    rs = gain / loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def build_signals(ticker: str, close: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"close": close})
    df["dma20"] = close.rolling(20).mean()
    df["dma50"] = close.rolling(50).mean()
    df["rsi"] = rsi(close, 14)
    df["next_ret"] = close.shift(-1) / close - 1.0

    def verdict(row) -> str:
        if pd.isna(row.dma50) or pd.isna(row.rsi):
            return ""
        up = row.close > row.dma50 and row.dma20 > row.dma50
        down = row.close < row.dma50 and row.dma20 < row.dma50
        if up and row.rsi < 70:
            return "BUY"
        if down or row.rsi > 75:
            return "SELL"
        return "HOLD"

    df["verdict"] = df.apply(verdict, axis=1)

    def grade(row) -> str:
        if row.verdict == "" or pd.isna(row.next_ret):
            return ""
        r = row.next_ret
        if row.verdict == "BUY":
            return "Correct" if r > BUY_HIT else "Wrong"
        if row.verdict == "SELL":
            return "Correct" if r < SELL_HIT else "Wrong"
        return "Correct" if abs(r) <= HOLD_BAND else "Wrong"

    df["outcome"] = df.apply(grade, axis=1)
    df["ticker"] = ticker
    df = df.reset_index().rename(columns={"Date": "date", "index": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df


def main() -> None:
    print(f"InvestAI backtest — {PERIOD} lookback, {len(UNIVERSE)} instruments\n")

    frames = []
    for t in UNIVERSE:
        close = fetch_close(f"{t}.NS")
        if close is None:
            print(f"  ! {t}: no data, skipping")
            continue
        frames.append(build_signals(t, close))
        print(f"  ok {t}: {len(close)} days")

    signals = pd.concat(frames, ignore_index=True)
    # Only rows with a definite verdict AND a known next-day outcome are scorable.
    scored = signals[(signals.verdict != "") & (signals.outcome != "")].copy()

    bench_close = fetch_close(BENCHMARK)
    bench = pd.DataFrame({"close": bench_close}).reset_index()
    bench.columns = ["date", "close"]
    bench["date"] = pd.to_datetime(bench["date"]).dt.strftime("%Y-%m-%d")

    # ---- accuracy ----
    n_calls = len(scored)
    n_correct = int((scored.outcome == "Correct").sum())
    accuracy = round(100 * n_correct / n_calls, 1) if n_calls else 0.0
    by_verdict = {}
    for v in ["BUY", "SELL", "HOLD"]:
        sub = scored[scored.verdict == v]
        by_verdict[v] = {
            "calls": int(len(sub)),
            "accuracy": round(100 * (sub.outcome == "Correct").mean(), 1) if len(sub) else None,
        }

    # ---- strategy equity curve: long-only equal-weight BUY basket ----
    daily = (
        scored[scored.verdict == "BUY"].groupby("date")["next_ret"].mean()
    )  # mean next-day return of names rated BUY that day
    all_dates = sorted(scored["date"].unique())
    strat_ret = pd.Series(0.0, index=all_dates)
    strat_ret.update(daily)  # days with no BUY stay 0 (cash)
    strat_equity = (1 + strat_ret).cumprod()

    # benchmark over the same window
    bench_win = bench[bench.date.isin(all_dates)].sort_values("date").reset_index(drop=True)
    bench_equity = bench_win["close"] / bench_win["close"].iloc[0]
    bench_equity.index = bench_win["date"]

    strat_final = round(100 * (strat_equity.iloc[-1] - 1), 1)
    bench_final = round(100 * (bench_equity.iloc[-1] - 1), 1)

    # max drawdown of the strategy
    running_max = strat_equity.cummax()
    drawdown = strat_equity / running_max - 1
    max_dd = round(100 * drawdown.min(), 1)

    # ---- per-instrument hit rate ----
    per_instrument = []
    for t, sub in scored.groupby("ticker"):
        per_instrument.append({
            "ticker": t,
            "calls": int(len(sub)),
            "accuracy": round(100 * (sub.outcome == "Correct").mean(), 1),
        })
    per_instrument.sort(key=lambda x: x["accuracy"], reverse=True)

    # ---- equity curve series (small) ----
    curve = []
    for d in all_dates:
        b = bench_equity.get(d)
        curve.append({
            "date": d,
            "strategy": round(float(strat_equity[d]), 4),
            "benchmark": round(float(b), 4) if b is not None and not pd.isna(b) else None,
        })

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "technical-baseline",
        "lookback": PERIOD,
        "period": {"start": all_dates[0], "end": all_dates[-1]},
        "n_instruments": signals["ticker"].nunique(),
        "n_calls": n_calls,
        "accuracy_pct": accuracy,
        "by_verdict": by_verdict,
        "strategy_return_pct": strat_final,
        "benchmark_return_pct": bench_final,
        "outperformance_pct": round(strat_final - bench_final, 1),
        "max_drawdown_pct": max_dd,
        "equity_curve": curve,
        "per_instrument": per_instrument,
        "disclaimer": (
            "Technical-baseline backtest (trend + RSI), graded with the live agent's "
            "thresholds and benchmarked vs NIFTY 50 buy-and-hold. NOT a replay of the "
            "LLM agent. Long-only BUY basket. Past performance is not indicative of "
            "future results; research/education only."
        ),
    }

    # ---- write heavy base tables to local SQLite (stays on the PC) ----
    con = sqlite3.connect(DB_PATH)
    signals.to_sql("signals", con, if_exists="replace", index=False)
    bench.to_sql("benchmark", con, if_exists="replace", index=False)
    con.close()

    # ---- write tiny summary for the dashboard ----
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== RESULT ===")
    print(f"Period         : {all_dates[0]} -> {all_dates[-1]}  ({len(all_dates)} trading days)")
    print(f"Calls graded   : {n_calls}  (accuracy {accuracy}%)")
    print(f"  BUY  {by_verdict['BUY']}")
    print(f"  SELL {by_verdict['SELL']}")
    print(f"  HOLD {by_verdict['HOLD']}")
    print(f"Strategy return: {strat_final}%   NIFTY: {bench_final}%   (alpha {summary['outperformance_pct']}%)")
    print(f"Max drawdown   : {max_dd}%")
    print(f"\nBase tables -> {DB_PATH}")
    print(f"Summary     -> {JSON_PATH}")


if __name__ == "__main__":
    main()
