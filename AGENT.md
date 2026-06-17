# InvestAI — 12-Stock Daily Agent (source of truth)

Version-controlled definition of the live Anthropic-cloud routine. The routine
itself is the running copy (saved server-side); this file is the reviewable
source. Edit here, then mirror changes into the routine via the `/schedule`
RemoteTrigger `update` action.

## Where it runs
- **Cloud routine** (Anthropic cloud, runs on the Claude plan — no API key):
  - id: `trig_01SYmjbgEdjKHhQpFozrfJjZ`
  - name: `InvestAI 12-Stock Daily Agent`
  - schedule: `0 3 * * *` UTC = **08:30 IST daily**
  - model: `claude-sonnet-4-6`
  - manage: https://claude.ai/code/routines/trig_01SYmjbgEdjKHhQpFozrfJjZ

## The 12 stocks (fixed universe, NSE)
RELIANCE, HDFCBANK, ICICIBANK, TCS, INFY, BHARTIARTL, ITC, HINDUNILVR, LT,
MARUTI, SUNPHARMA, TATASTEEL. (yfinance: append `.NS`.) No other tickers are
ever referenced — the Replacement-Stock agent is intentionally disabled.

## Memory = Notion (page "INVESTAI")
- page id: `3824a313-fee2-81a8-b70c-f5ecf2183fe3`
- **Recommendations** data source: `8f225b65-31b3-4f12-9700-34e7a2a459e0`
  - Entry(title), Date, Ticker, Company, Verdict(BUY/HOLD/SELL),
    Category, Composite Score, Expected Direction(Up/Down/Flat), Ref Price,
    Fundamental, Technical, Valuation, Macro, Sentiment, Risk, Sources,
    Outcome(Correct/Wrong/Pending), Actual Move %
- **Daily Review** data source: `a69929f7-e386-4d9a-bf60-16f468dd4325`
  - Day(title), Date, Stocks Evaluated, Correct, Accuracy %, Self Rating,
    Correctable Errors, Market-Driven Misses, Lessons, Summary

## Scoring framework
Weighted composite (0-100): **Fundamental 30 · Technical 20 · Valuation 20 ·
Macro 15 · Sentiment 5 · Risk 10**. Risk has veto power.

Categories → verdict:
- Strong Buy (>80) → BUY
- Buy on Dip (70-80) → BUY
- Watchlist (60-70) → HOLD
- Hold (45-60) → HOLD
- Avoid/Sell (<45) → SELL

## Data sources
- Prices / technicals: `yfinance` (`<SYM>.NS`) — works on datacenter IP.
- Fundamentals / valuation: screener.in / Tickertape / Moneycontrol (WebFetch).
- Macro / geopolitics: WebSearch.
- Sentiment (trusted YouTube channels, lowest weight): the public file
  `https://raw.githubusercontent.com/Sanjaycsk/youtube-stock-reader/main/data/transcripts.json`
  produced by the home-PC project `youtube-stock-reader`. Freshness rule: if its
  `last_updated` != today, the brief notes YouTube wasn't fresh and uses news only.

## Daily loop
1. **Review & grade yesterday** — pull `Outcome = Pending` rows, fetch actual
   closes, mark Correct/Wrong + Actual Move %, compute Accuracy % and Self
   Rating /100, classify misses (correctable vs market), write a Daily Review row.
2. **Analyze today** — 6-factor weighted score per stock → category → verdict.
3. **Log today** — one Recommendations row per stock, `Outcome = Pending`.

## Phasing
- **Phase 1 (live):** the loop above.
- **Phase 2:** deeper Fundamental/Valuation (weekly refresh) + historical-pattern
  reasoning + source-reliability tables.
- **Phase 3:** learning weight-adjustment (meaningful after ~2 weeks of data).
- **Deferred:** Telegram end-of-run delivery.

## The exact routine prompt
The live prompt sent to the cloud routine is mirrored in
[`agent/routine_prompt.md`](agent/routine_prompt.md).
