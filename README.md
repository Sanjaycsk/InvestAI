# InvestAI — Self-Grading Stock Research Agent

A daily, **autonomous** equity-research agent built on **Claude (Anthropic)**. Every
morning it issues a **BUY / HOLD / SELL** verdict on a fixed 24-instrument NSE
watchlist, then **grades its own previous calls against what actually happened**,
scores its accuracy, and learns from its mistakes — with every decision logged and
auditable.

> 📊 **Trust comes from accountability, not "the AI said so."** Every call is graded
> against reality, logged with its reasoning, and the method is version-controlled
> and open to inspection. A human makes every actual decision — the agent **never trades.**

📄 **Shareable explainer:** [`docs/how-it-works.html`](docs/how-it-works.html) ·
📐 **Architecture diagram:** [`docs/architecture-diagram.svg`](docs/architecture-diagram.svg) ·
🧠 **Agent definition (source of truth):** [`AGENT.md`](AGENT.md)

---

## How it works (the daily loop)

Runs unattended each morning (08:30 IST) as a scheduled **Claude cloud agent** —
on the Claude plan, no API key:

1. **Review & grade yesterday** — pull each pending call, read the actual close, mark
   it Correct/Wrong, compute accuracy % and a self-rating /100.
2. **Learn** — read the last ~5 daily reviews and apply their *correctable-error*
   lessons as standing rules for today (genuine market-driven misses are left alone).
3. **Analyze today** — score six factors per instrument and combine with weights tuned
   to each instrument type.
4. **Decide & log** — map the composite score to a category and a verdict, and write it
   (with the reasoning for every factor) to the Notion audit database.

Full, verbatim instructions: [`agent/routine_prompt.md`](agent/routine_prompt.md).

### Scoring (equities)
Fundamental 30 · Technical 20 · Valuation 20 · Macro 15 · Sentiment 5 · Risk 10 (Risk
can veto). Commodity & index ETFs use type-specific weights. Composite 0–100 →
Strong Buy (>80) / Buy on Dip (70–80) / Watchlist (60–70) / Hold (45–60) / Avoid·Sell (<45).

---

## Architecture

Four cooperating environments, each chosen for where its data is actually reachable:

```
YouTube ─▶ Home PC (residential) ─▶ Public GitHub ─┐
                                                    ▼
            Live Web ──────────────▶  CLAUDE CLOUD AGENT  ⇄  Notion (audit memory)
                                      (review · learn ·            │
                                       analyze · decide)           ▼
                                                              You (decide)
```

- **Home PC** — fetches transcripts from trusted YouTube channels (YouTube only loads
  from a residential IP). Companion repo: **[youtube-stock-reader](https://github.com/Sanjaycsk/youtube-stock-reader)**.
- **Public GitHub** — holds the transcript data feed + the version-controlled agent prompt.
- **Anthropic cloud** — the Claude agent reads the data, researches the live web, runs
  the analysis, and grades itself. Model: `Claude Sonnet 4.6`.
- **Notion** — the permanent, human-readable audit trail (`Recommendations` +
  `Daily Review`).

See [`AGENT.md`](AGENT.md) for IDs, schema, and the exact wiring.

---

## The 24 instruments (fixed universe, NSE)

**Equities (21):** RELIANCE, HDFCBANK, ICICIBANK, TCS, INFY, BHARTIARTL, ITC,
HINDUNILVR, LT, MARUTI, SUNPHARMA, TATASTEEL, SBIN, FEDERALBNK, SUZLON, TATAPOWER,
WAAREEENER, NTPC, ADANIENT, BEL, BHEL
**Index ETF (1):** GROWWN200 (Groww Nifty 200 ETF — market proxy)
**Commodity ETFs (2):** GOLDBEES (Gold), SILVERBEES (Silver)

---

## Why it can be trusted

- **Held accountable daily** — every call is checked against the real close and scored;
  wins *and* losses are recorded.
- **Fully auditable** — each recommendation is stored with its reasoning, sources, and a
  timestamp; nothing is ephemeral.
- **Learns from mistakes** — errors are classified (fixable vs market) and fixable ones
  become rules it applies the next day.
- **No black box** — the agent's exact instructions are version-controlled here.
- **Human-in-the-loop** — it only suggests; a person decides. It never auto-trades.

### Honest limits
Markets are uncertain; it uses only public data (no insider/private feeds); it is a
once-daily (not intraday) tool; and it is **research/education only — not financial advice.**

---

## Repository layout

```
AGENT.md                     source-of-truth for the live cloud agent
agent/routine_prompt.md      the exact prompt the agent runs (mirror of the routine)
docs/how-it-works.html       shareable, non-technical explainer
docs/architecture-diagram.svg  editable vector diagram (Figma-importable)
config/  src/  scripts/  tests/   original local Python toolkit (200-DMA, RSS,
                                   discovery, simulated execution) — the prototype
                                   this evolved from; kept for local/offline use.
```

> The original Python pipeline (the earlier discovery/portfolio prototype) still runs
> locally and offline, but the **live system is the Claude cloud agent** described above.

---

## Status

A **45-day evaluation** of the agent's daily accuracy is underway. Telegram delivery of
the daily brief is deferred; results currently land in the Notion audit database and the
routine's run history.
