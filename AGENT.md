# InvestAI — Multi-Run Daily Agent (source of truth)

Version-controlled definition of the live Anthropic-cloud routines. The routines
themselves are the running copies (saved server-side); this file is the reviewable
source. Edit here, then mirror changes into a routine via the `/schedule`
RemoteTrigger `update` action.

## Where it runs — three cloud routines (Claude plan, no API key, model `claude-sonnet-4-6`)

All crons are **UTC**; the local time is **IST** (UTC+5:30). All run **weekdays only**
(`* * 1-5`) and each begins with a **trading-day gate** that also skips NSE holidays
(see list below).

| Routine | id | cron (UTC) | IST | Role |
| --- | --- | --- | --- | --- |
| **Run 1 · Pre-market** | `trig_01SYmjbgEdjKHhQpFozrfJjZ` | `0 3 * * 1-5` | 08:30 | grade yesterday (+ mgmt alpha) → learn → analyze 24 → log verdict (frozen) → **STEP 4 coffee debate** |
| **Run 2 · Confirm** | `trig_01JJVmRfagEaGxnLpUNgNa8f` | `30 4 * * 1-5` | 10:00 | delta-check vs morning thesis; reads friend Inputs; annotates `Run2*` → **coffee debate** |
| **Run 3 · De-risk** | `trig_018n6MbVkChwJmf13aDWqm2W` | `30 9 * * 1-5` | 15:00 | exit/trim only on a material break; annotates `Run3*` + `Exit Price` → **coffee debate** |

The six-persona coffee-shop debate is folded into each run as its final step (STEP 4) —
so there are **three** triggers, not six. The earlier standalone coffee routines
(`trig_01Ak5QL1HPRVzZ5coL8pzY6n`, `trig_0129grinVncDPyHXA14JXTGQ`, `trig_0146ujGThP7hYDdTu9FAeqzv`)
are now **disabled** (delete them at https://claude.ai/code/routines).

Each routine's `session_context.allowed_tools` **must** keep `mcp__Notion` (the Notion
connector is attached to all six). `job_config` updates replace the whole object, so
resend the full prompt verbatim when editing.

## The 24 instruments (fixed universe, NSE)
**Equities (21):** RELIANCE, HDFCBANK, ICICIBANK, TCS, INFY, BHARTIARTL, ITC,
HINDUNILVR, LT, MARUTI, SUNPHARMA, TATASTEEL, SBIN, FEDERALBNK, SUZLON,
TATAPOWER, WAAREEENER, NTPC, ADANIENT, BEL, BHEL.
**Index ETF (1):** GROWWN200 (Groww Nifty 200 ETF — broad-market proxy).
**Commodity ETFs (2):** GOLDBEES (Gold ETF), SILVERBEES (Silver ETF).
No other tickers are ever referenced — the Replacement-Stock agent is disabled.

## Trading-day gate (NSE 2026 holidays)
Every run skips weekends and these dates (prints "Market holiday — skipped" and exits):
`2026-01-26, 2026-03-03, 2026-03-26, 2026-03-31, 2026-04-03, 2026-04-14, 2026-05-01,
2026-05-28, 2026-06-26, 2026-09-14, 2026-10-02, 2026-10-20, 2026-11-10, 2026-11-24,
2026-12-25`. (Nov 08 has special Muhurat trading — handle separately if needed.)

## Memory = Notion (page "INVESTAI", id `3824a313-fee2-81a8-b70c-f5ecf2183fe3`)

**Recommendations** — `8f225b65-31b3-4f12-9700-34e7a2a459e0`
- Run 1 (frozen verdict of record): Entry(title), Date, Ticker, Company,
  Verdict(BUY/HOLD/SELL), Category, Composite Score, Expected Direction(Up/Down/Flat),
  Ref Price, Fundamental, Technical, Valuation, Macro, Sentiment, Risk, Sources,
  Outcome(Correct/Wrong/Pending), Actual Move %.
- Run 2 annotations: **Run2 Status**(Intact/Weakening/Broken), **Run2 Action**(None/Watch),
  **Run2 Note**, **Run2 Price**.
- Run 3 annotations: **Run3 Status**, **Run3 Action**(None/Trim/Exit), **Run3 Note**,
  **Run3 Price**, **Exit Price**, **Mgmt Saved** (Exit Price − actual close, graded next morning).

**Daily Review** — `a69929f7-e386-4d9a-bf60-16f468dd4325`
- Day(title), Date, Stocks Evaluated, Correct, Accuracy %, Self Rating, Correctable
  Errors, Market-Driven Misses, Lessons, Summary, **Mgmt Alpha** (sum of Mgmt Saved),
  **Exits Count**.

**Inputs (Run 2 — 10:00 IST)** — `a8288c20-969a-4962-a016-1fadd1f3738f`
- A friend drops free-text market notes here: **Info**(title) + **Date**(created_time, auto).
  Run 2 reads today's rows, keeps only ones touching the 24 (ignores other tickers),
  treats them as soft signal.

**Coffee Shop (Run 1 panel)** — `fee73e14-f1c4-48b7-a285-c319ccb781b7`
- Note(title), Date, Ticker, **Persona**(Vihaan/Aarav/Rohan/Meera/Neel/Diya),
  **Stance**(Buy/SIP/Hold/Wait/Avoid/Punt), **Horizon**(Long/Short/Mixed), Take,
  **Debate**(per-ticker transcript, written on that ticker's Vihaan row),
  **Run**(Pre-market/Confirm/De-risk). One row per persona × shortlisted ticker × run.

## Scoring framework
Weighted composite (0-100), weights depend on instrument type. Risk has veto power.
- **Equities (21):** Fundamental 30 · Technical 20 · Valuation 20 · Macro 15 · Sentiment 5 · Risk 10
- **Index ETF (GROWWN200):** Fundamental N/A → Macro 40 · Technical 35 · Valuation 15 · Sentiment 10
- **Commodity ETFs (GOLDBEES, SILVERBEES):** Fundamental/Valuation N/A → Technical 35 · Macro 30 · Sentiment 25 · Risk 10

Categories → verdict: Strong Buy (>80) → BUY · Buy on Dip (70-80) → BUY ·
Watchlist (60-70) → HOLD · Hold (45-60) → HOLD · Avoid/Sell (<45) → SELL.

## The grading split (why accuracy stays honest)
- **Verdict / Expected Direction / Ref Price are frozen after Run 1.** Runs 2 & 3 read
  them but never change them — they only write the `Run2*`/`Run3*` columns.
- **Forecast accuracy** (the 45-day headline) is graded against **Run 1's verdict only**.
- **Management alpha** is a separate scorecard: for any prior-day `Run3 Action = Exit/Trim`,
  `Mgmt Saved = Exit Price − actual close`; summed onto Daily Review as `Mgmt Alpha`. It
  measures whether de-risking helps and **never** touches the BUY/HOLD/SELL grading.

## Data sources
- Prices / technicals: **WEB only** (Google Finance / Moneycontrol / Tickertape /
  Investing / NSE). ⚠️ **yfinance/Yahoo is BLOCKED in the Anthropic cloud sandbox** —
  do NOT use it; read the published price/RSI/MACD/DMA numbers off the sites.
- Fundamentals / valuation: screener.in / Tickertape / Moneycontrol (WebFetch).
- Macro / geopolitics: WebSearch.
- Sentiment (trusted YouTube channels, lowest weight): the public file
  `https://raw.githubusercontent.com/Sanjaycsk/youtube-stock-reader/main/data/transcripts.json`
  produced by the home-PC project `youtube-stock-reader`. Freshness rule: if its
  `last_updated` != today, the brief notes YouTube wasn't fresh and uses news only.

## The day's loop
**Run 1 (08:30)** — STEP 0 trading-day gate · STEP 1 grade yesterday's Pending rows
(+ management alpha) → Daily Review row · STEP 1.5 learn from recent reviews · STEP 2
per-type 6-factor score → category → verdict · STEP 3 log one Recommendations row per
instrument (overwrite-safe; verdict frozen) · STEP 4 coffee debate (Pre-market).
**Run 2 (10:00)** — gate · load today's verdicts · read friend Inputs (today, our 24
only) · pull intraday prices · write `Run2 Status/Action/Note/Price` (mostly "Intact / None")
· STEP 4 coffee debate (Confirm).
**Run 3 (15:00)** — gate · load verdicts + Run 2 reads · exit/trim only on a material
thesis break · write `Run3 Status/Action/Note/Price` + `Exit Price` · STEP 4 coffee debate (De-risk).
**STEP 4 coffee debate (inside every run)** — take the day's top-5 BUY shortlist; the 6
characters argue back-and-forth (rebutting each other by name) and each records a stance
into Coffee Shop tagged with the run; the per-ticker transcript goes in the `Debate`
column (on that ticker's Vihaan row). Perspective only — never changes the verdict.

## Logging is overwrite-safe
Re-running a given day **updates** that day's rows (Recommendations keyed by Date+Ticker;
Coffee Shop keyed by Date+Ticker+Persona+Run) instead of duplicating.

## Phasing
- **Phase 1 (live):** the multi-run loop + coffee-shop perspective panel above.
- **Phase 2:** deeper Fundamental/Valuation (weekly refresh) + historical-pattern
  reasoning + source-reliability tables.
- **Phase 3:** learning weight-adjustment (meaningful after ~2 weeks of data).
- **Deferred:** Telegram end-of-run delivery.

## The exact routine prompts
Run 1's verbatim prompt is mirrored in [`agent/routine_prompt.md`](agent/routine_prompt.md)
(including its STEP 4 coffee debate); Runs 2 and 3 are summarised there and live server-side
under the IDs above.
