# InvestAI — Multi-Run Daily Agent (source of truth)

Version-controlled definition of the live Anthropic-cloud routines. The routines
themselves are the running copies (saved server-side); this file is the reviewable
source. Edit here, then mirror changes into a routine via the `/schedule`
RemoteTrigger `update` action.

## Where it runs — three cloud routines (Claude plan, no API key, model `claude-sonnet-4-6`)

All crons are **UTC**; the local time is **IST** (UTC+5:30). All run **weekdays only**
(`* * 1-5`) and each begins with a **trading-day gate** that also skips NSE holidays
(see list below).

Routine names shown here are the friendly labels; the **actual name in the claude.ai
routines UI** is in the "UI name" column. Keep the UI names' instrument count in sync
(rename "(24 instruments)" → "(26 instruments)" after the VEDL/BPCL change).

| Routine | UI name (claude.ai) | id | cron (UTC) | IST | Role |
| --- | --- | --- | --- | --- | --- |
| **Run 1 · Pre-market** | `InvestAI Daily Agent (26 instruments)` | `trig_01SYmjbgEdjKHhQpFozrfJjZ` | `0 3 * * 1-5` | 08:30 | grade yesterday (+ mgmt alpha) → learn → analyze 26 → log verdict (frozen) → **STEP 4 coffee debate** |
| **Run 2 · Confirm** | _(confirm in UI)_ | `trig_01JJVmRfagEaGxnLpUNgNa8f` | `30 4 * * 1-5` | 10:00 | delta-check vs morning thesis; reads friend Inputs; annotates `Run2*` → **coffee debate** |
| **Run 3 · De-risk** | _(confirm in UI)_ | `trig_018n6MbVkChwJmf13aDWqm2W` | `30 9 * * 1-5` | 15:00 | exit/trim only on a material break; annotates `Run3*` + `Exit Price` → **coffee debate** |

The six-persona coffee-shop debate is folded into each run as its final step (STEP 4) —
so there are **three** triggers, not six. The earlier standalone coffee routines
(`trig_01Ak5QL1HPRVzZ5coL8pzY6n`, `trig_0129grinVncDPyHXA14JXTGQ`, `trig_0146ujGThP7hYDdTu9FAeqzv`)
are now **disabled** (delete them at https://claude.ai/code/routines).

Each routine's `session_context.allowed_tools` **must** keep `mcp__Notion` (the Notion
connector is attached to all six). `job_config` updates replace the whole object, so
resend the full prompt verbatim when editing.

## The 26 instruments (fixed universe, NSE)
**Equities (23):** RELIANCE, HDFCBANK, ICICIBANK, TCS, INFY, BHARTIARTL, ITC,
HINDUNILVR, LT, MARUTI, SUNPHARMA, TATASTEEL, SBIN, FEDERALBNK, SUZLON,
TATAPOWER, WAAREEENER, NTPC, ADANIENT, BEL, BHEL, VEDL, BPCL.
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
  **Exits Count**, **Nifty Close** (number), **Nifty Move %** (number) — the last two
  are NEW (2026-08-11) and need to be added to this database in Notion (Number type)
  before Run 1 can populate them; the prompt falls back gracefully if they're missing
  (see Step 1.6's DEFENSIVE FALLBACK), and the dashboard falls back to a GROWWN200-based
  proxy until they start getting filled in. **Owner action needed**: add these two
  columns once in the Daily Review database.

**Inputs (Run 2 — 10:00 IST)** — `a8288c20-969a-4962-a016-1fadd1f3738f`
- A friend drops free-text market notes here: **Info**(title) + **Date**(created_time, auto).
  Run 2 reads today's rows, keeps only ones touching the 26 (ignores other tickers),
  treats them as soft signal.

**Coffee Shop (Run 1 panel)** — `fee73e14-f1c4-48b7-a285-c319ccb781b7`
- Note(title), Date, Ticker, **Persona**(Vihaan/Aarav/Rohan/Meera/Neel/Diya),
  **Stance**(Buy/SIP/Hold/Wait/Avoid/Punt), **Horizon**(Long/Short/Mixed), Take,
  **Debate**(per-ticker transcript, written on that ticker's Vihaan row),
  **Run**(Pre-market/Confirm/De-risk). One row per persona × shortlisted ticker × run.

## Scoring framework
Weighted composite (0-100), weights depend on instrument type. Risk has veto power.
- **Equities (23):** Fundamental 30 · Technical 20 · Valuation 20 · Macro 15 · Sentiment 5 · Risk 10
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
- Prices / technicals: **PRIMARY = `prices.json`**, the home-published clean
  yfinance EOD feed (close/prev/DMA20-50-200/RSI14/52w/recent_closes for all 26 +
  a NIFTY benchmark) at
  `https://raw.githubusercontent.com/Sanjaycsk/youtube-stock-reader/main/data/prices.json`
  — produced by `youtube-stock-reader/fetch_prices.py` (same home-PC bridge as the
  transcripts, since ⚠️ **yfinance/Yahoo is BLOCKED in the Anthropic cloud sandbox**).
  Trust these numbers over web quotes; this replaced the flaky web-scraping that
  had logged wrong Ref Prices. Web (Google Finance / Moneycontrol / Tickertape /
  NSE) is now only a FALLBACK for a missing/stale ticker or for MACD / support-
  resistance / volume that prices.json doesn't carry. Freshness: check `last_updated`.
- Fundamentals / valuation: screener.in / Tickertape / Moneycontrol (WebFetch).
- Macro / geopolitics: WebSearch.
- Sentiment (trusted YouTube channels, lowest weight): the public file
  `https://raw.githubusercontent.com/Sanjaycsk/youtube-stock-reader/main/data/transcripts.json`
  produced by the home-PC project `youtube-stock-reader`. Freshness rule: if its
  `last_updated` != today, the brief notes YouTube wasn't fresh and uses news only.

## The day's loop
**Run 1 (08:30)** — STEP 0 trading-day gate · STEP 1 grade yesterday's Pending rows
(+ management alpha, + a self-incentive check against a 75% accuracy bar as its last
sub-step, which sets how strictly today's lessons get applied) → Daily Review row ·
STEP 1.5 learn from recent reviews · STEP 2 per-type 6-factor score → category → verdict
· STEP 3 log one Recommendations row per instrument (overwrite-safe; verdict frozen) ·
STEP 4 coffee debate (Pre-market).
**Run 2 (10:00)** — gate · load today's verdicts · read friend Inputs (today, our 26
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

## 2026-08 audit — what changed and why
Queried the live Recommendations/Daily Review data sources directly (733 graded
rows, 2026-06-17 to 2026-07-31). Findings, applied to `agent/routine_prompt.md`
+ `RUN1_prompt_ready_to_paste.txt` (paste the latter into the Run 1 routine to
go live — see [`agent/routine_prompt.md`](agent/routine_prompt.md) header):
- **Ref-price errors are still recurring** despite the existing sanity gates —
  Daily Review Lessons flagged a stale/wrong ref price on the large majority of
  days in the window (BEL, WAAREEENER, RELIANCE, TATASTEEL, FEDERALBNK, MARUTI,
  HINDUNILVR...), and several graded rows carry physically impossible moves
  (WAAREEENER +934%, FEDERALBNK +136%, HDFCBANK -59%/-57%/-55%/-53% on separate
  days) that the existing ±20% gate should have caught but didn't. Tightened
  both gates to ±15% / 2-source-agreement-within-2%/cite-sources-or-stay-Pending,
  and added a REPEATED-ERROR ESCALATION rule (2+ flags in 5 days -> stop using
  the web fallback for that ticker, use prices.json only).
- **Composite Score is not reliably monotonic with accuracy**: Watchlist
  (60-70) is the best-calibrated band (78% correct, n=224); Buy on Dip (70-80)
  underperformed (46% correct, net-negative average move, n=35); Strong Buy
  (>80) is too thin to trust (n=5). Added a CALIBRATION REALITY CHECK to Step
  1.5 so a high score is treated as a reason to double-check, not extra
  confidence, until re-audited on cleaner data.
- **Results-day misses are a recurring, avoidable pattern** (SUZLON -8.5%,
  MARUTI +12.1%, HINDUNILVR -13.5% intraday, ADANIENT, BEL). Added a
  RESULTS-DAY GATE to Step 2 that checks for a confirmed quarterly-results date
  and caps Category at Watchlist on event-risk days.
- **Lessons text grows unboundedly** (L1...L61+ by end of July with no
  pruning) — likely contributing to accuracy drifting from ~76% (June) to ~65%
  (July) within the window. Added a LESSON HYGIENE instruction: consolidate/dedupe
  every ~10 trading days instead of only appending.
- **No position sizing or stop-loss exists in the live system at all** — it is
  purely a directional forecast + a separate Mgmt Alpha scorecard for Run 3's
  exit/trim calls (which fired only 3 times in the window and lost money every
  time it did, though n=3 is too small to conclude much). The reported "loss"
  is the paper-accuracy/Mgmt-Alpha track record getting worse, not real trading
  capital — `EXECUTION_ENABLED` is still False. A conviction-scaled
  position-sizing + stop-loss engine (`src/analysis/position_sizing.py`,
  `src/analysis/calibration.py`, `src/data/price_data.get_verified_price`,
  `src/execution/order_manager.check_stop_loss`) now exists in this repo for
  when real sizing is eventually wanted, fit on the same empirical hit-rates
  above — it is NOT yet wired into the live cloud routine (the routine has no
  Suggested Qty concept today), and this repo is still not GitHub-authorized
  for the cloud routine to read.
- **ETF instrument-type-aware scoring already existed correctly in the live
  prompt** (this repo's `src/analysis/scoring.py` + `instruments.py` were
  corrected to match it exactly, not the other way round).

## 2026-08-11 — TradingAgents-inspired memory & calibration upgrade
Cloned and read [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) — a LangGraph
multi-agent trading framework: per-role analysts -> bull/bear researcher debate -> research
manager verdict -> trader -> aggressive/conservative/neutral risk debate -> portfolio manager,
plus an append-only reflection log keyed by ticker+date with a same-ticker/cross-ticker memory
split (`n_same`/`n_cross`) and a deterministic entry-count rotation cap. InvestAI is one
sequential Claude routine, not a LangGraph multi-agent graph, so most of that architecture
doesn't transfer directly — but three ideas did, applied to `agent/routine_prompt.md` /
`RUN1_prompt_ready_to_paste.txt` (Run 1 only; Run 2/Run 3 unchanged):
- **Ticker-tagged lessons + same-ticker recall** (was: one flat pool of the last ~5 Daily
  Review rows' Lessons/Correctable Errors, generic across all 26). Every Correctable Error /
  Market-Driven Miss / Lesson line is now tagged `TICKER: text` (or `ALL: text` for
  system-wide rules), and Step 1.5 does a same-ticker vs cross-ticker recall over the last
  ~10 rows — mirrors `TradingMemoryLog.get_past_context`'s `n_same`/`n_cross` split. A name
  with 2+ recent same-ticker corrections is now flagged specifically instead of being
  diluted into the aggregate pool.
- **Deterministic lesson-count cap** (was: "every 10th trading day, use your judgment",
  capped at "roughly 20"). Now triggers whenever the standing count exceeds 20, checked on
  every run, hard-capped at exactly 20 — mirrors `TradingMemoryLog._apply_rotation`'s
  count-based rotation instead of a calendar guess.
- **Bull/bear pre-verdict check, scoped to boundary cases** (new). TradingAgents commits
  every verdict through a full bull-vs-bear debate; InvestAI can't spin up separate agents
  mid-routine, so this is a single self-adversarial reasoning step — one bull sentence, one
  bear sentence — applied only when a name's Composite Score is within 5 points of a
  Category boundary or lands in Strong Buy/Buy on Dip, the exact bands the 2026-08
  calibration audit above found overconfident. Not applied to all 26 (would triple Step 2's
  cost for no benefit on names that aren't close calls).
Not carried over: the full bull/bear/risk-debate architecture (needs a multi-agent graph
InvestAI doesn't have), position sizing (out of scope — no live capital), and a
risk-mgmt-style aggressive/conservative debate for Run 3's exit/trim call (Run 3's existing
OVERSOLD-PANIC CAUTION already encodes the same "don't panic-sell on noise" lesson from its
own 2-trim sample). The Coffee Shop 6-persona panel already covers a lighter version of
"multiple viewpoints" and is deliberately kept perspective-only so it can't be tempted into
re-fighting the frozen verdict.

## 2026-08-11 (part 2) — owner feedback: real Nifty, regime awareness, simpler language, dashboard v2
Direct owner feedback on the live dashboard, addressed same day:
- **Real Nifty 50, not just the GROWWN200 proxy.** Discovered `prices.json` already carries
  a `benchmarks.NIFTY50` reading (`close`, `change_pct`) separate from the GROWWN200
  instrument (a Nifty 200 ETF — a different index). Run 1 Step 1.6 now logs it onto the
  Daily Review row as **Nifty Close** / **Nifty Move %**, with a defensive fallback (retry
  without those two fields) since the columns don't exist in Notion yet — **owner action
  needed**: add them (Number type) to the Daily Review database once. The dashboard's
  "Beating the market?" panel already prefers real Nifty when present and falls back to
  GROWWN200 automatically, so nothing else needs to change once the columns are added.
- **Market regime awareness** (Step 2, Run 1 only): a per-run Bullish/Bearish/Sideways read
  from GROWWN200's DMA position + RSI + yesterday's verdict breadth, stated in OUTPUT. In a
  Bearish regime the model is now explicitly told to look harder for genuine SELL/Avoid
  conviction and for real defensive setups (Gold/Silver safe-haven demand, genuine
  oversold buy-the-dip) instead of defaulting to a bullish playbook regardless of tape —
  reassessed fresh every run, not a standing bias.
- **10th-grade reading level, explicitly**, tightened in all three runs' Step 4 (was an
  18-word/line guideline only in Run 1; now a 15-word/line cap with a stated reading-level
  bar in Run 1, 2, and 3).
- **Dashboard v2** (`dashboard/`): decluttered per "overwhelmed with data" feedback.
  - Coffee Shop is no longer a separate tab — folded into the per-stock lookup instead
    (`StockLookup.tsx`), so it only appears when you actually pick that stock.
  - The "Look up any stock" picker moved off the home page onto its own second tab
    (`/lookup`, was `/coffee`), where picking a stock now also shows yesterday's call,
    its own all-time hit-rate (`tickerStats`), and the coffee-shop opinions for it —
    instead of those three things being scattered/absent.
  - New **Error Management** panel on the home page, positioned *before* Today's calls
    on purpose — surfaces Daily Review's Correctable Errors / Market-Driven Misses /
    standing Lessons, which existed in Notion but were never rendered anywhere.
  - Old self-grading "How often it's been right" line chart removed (already flagged
    unhelpful); its slot became the "Beating the market?" panel from earlier the same day.

## 2026-08-11 (part 3) / 2026-08-12 — self-incentive step, personalization, honest research dead-end
- **Run 1 gains a self-incentive check**, the last sub-step of STEP 1: states whether
  today's Accuracy % cleared a 75% bar in one OUTPUT line, then feeds that into how
  strictly STEP 1.5's lessons get applied and the boundary-case bull/bear check — a
  run of sub-75% days should visibly tighten standards over following days rather than
  just get noted. Edited into `agent/routine_prompt.md` and
  `agent/RUN1_prompt_ready_to_paste.txt`; **not yet pushed to the live Run 1 routine** —
  needs a `/schedule` RemoteTrigger `update` before it takes effect server-side.
- **Dashboard personalization**: a per-viewer holdings toggle (`OwnBadge.tsx`,
  localStorage only, no accounts) labels each call as owned or not; a sector board
  (`SectorBoard.tsx`, `lib/sectors.ts`) rolls the 26 up into per-sector
  Bullish/Bearish/Mixed mood; a dynamic entry-window banner flags the 9:15-11:00 AM IST
  buying window vs a stale 8:30 AM verdict later in the day; a 7-day date filter
  (`DateFilter.tsx`) was added to the lookup tab.
- **Experimental trend-forecasting research** (`backtest/train_ml_trend.py`,
  `train_arima_trend.py`, `train_lstm_trend.py`): five honest attempts at 15/5-day
  directional forecasting (gradient boosting, ARIMA, GBM with richer features, LSTM).
  None beat a naive baseline on walk-forward accuracy. Initially the GBM output was
  wired into the dashboard (clearly labeled experimental, with its real accuracy shown);
  it and its per-stock chip were then **removed from the UI entirely** the next day —
  the walk-forward numbers weren't good enough to surface prominently. Scripts and
  output JSON stay in the repo as an honest research record, just not rendered.
- **Dashboard UI fixes**: a real Chromium paint bug in the accordion collapse (`0fr`
  grid) animation — a closed section with flex-wrap children (sector chips, KPI grid)
  could still paint a sliver of content below the header even though layout reported
  0 height; fixed with a `visibility` guard alongside the existing overflow/height
  collapse. Also removed the now-redundant accuracy mood badge (duplicated the Accuracy
  KPI card) and a duplicate standalone Gold & Silver panel (GOLDBEES/SILVERBEES already
  appear under Today's calls like every other instrument); "Browse a past day" and
  "Yesterday's scorecard" became collapsible dropdowns to match the rest of the app.

## The exact routine prompts
Run 1's verbatim prompt is mirrored in [`agent/routine_prompt.md`](agent/routine_prompt.md)
(including its STEP 4 coffee debate); Runs 2 and 3 are summarised there and live server-side
under the IDs above.
