import type { ReactNode } from "react";
import { getDashboard, type Rec } from "@/lib/notion";
import { plainify } from "@/lib/plain";
import EquityChart from "./EquityChart";
import TopBar from "./TopBar";
import TabNav from "./TabNav";
import Section from "./Section";
import Panel from "./Panel";
import StockDetail from "./StockDetail";
import {
  CircleArrowUp,
  CircleArrowDown,
  CircleMinus,
  Shield,
  Coins,
  Moon,
  Flame,
  TrendingUp,
  Activity,
  Gauge,
  History,
  AlertTriangle,
} from "./Icons";
import backtest from "@/data/backtest.json";

// Always render fresh from Notion.
export const dynamic = "force-dynamic";
export const revalidate = 0;

const COMMODITY_META: Record<string, { name: string }> = {
  GOLDBEES: { name: "Gold (GOLDBEES)" },
  SILVERBEES: { name: "Silver (SILVERBEES)" },
};

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

function signed(n: number | null, suffix = "%"): string {
  if (n === null) return "—";
  const s = n > 0 ? "+" : "";
  return `${s}${n.toFixed(1)}${suffix}`;
}

// Price the model used when it ran ("Ref Price"), shown so you can decide.
function fmtPrice(n: number | null): string {
  if (n === null) return "";
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

// A short "RELIANCE · TCS · INFY" line shown on a collapsed section header.
function tickerSummary(recs: Rec[]): string {
  return recs
    .map((r) => r.ticker)
    .filter((t): t is string => !!t)
    .join(" · ");
}

// Plain-English read of the model's expected direction for the day.
const DIR: Record<string, { arrow: string; text: string; cls: string }> = {
  Up: { arrow: "▲", text: "expects it to go up", cls: "pos" },
  Down: { arrow: "▼", text: "expects it to go down", cls: "neg" },
  Flat: { arrow: "▬", text: "expects little change", cls: "" },
};

// Is the Indian market closed today (weekend)? Computed in IST.
function isWeekendIST(): boolean {
  const d = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Kolkata",
    weekday: "short",
  }).format(new Date());
  return d === "Sat" || d === "Sun";
}

const VERDICT_WORD: Record<string, string> = {
  BUY: "Buy",
  SELL: "Sell / avoid",
  HOLD: "Hold",
};

// Conviction-weighted allocation across a basket (by composite score),
// rounded to whole percents that sum to 100 (largest-remainder method).
function allocations(recs: Rec[]): number[] {
  const w = recs.map((r) =>
    typeof r.compositeScore === "number" && r.compositeScore > 0
      ? r.compositeScore
      : 1
  );
  const total = w.reduce((a, b) => a + b, 0) || 1;
  const raw = w.map((x) => (x / total) * 100);
  const floored = raw.map((x) => Math.floor(x));
  let left = 100 - floored.reduce((a, b) => a + b, 0);
  const order = raw
    .map((x, i) => ({ i, frac: x - Math.floor(x) }))
    .sort((a, b) => b.frac - a.frac);
  const out = [...floored];
  for (let k = 0; k < order.length && left > 0; k++, left--) out[order[k].i]++;
  return out;
}

// Compact intraday progression for one stock: the 10:00 confirm run and the
// 3:00 PM de-risk run, shown only once those runs have written something.
// Run 1's morning verdict stays the headline; this is just "what happened next".
function IntradayTimeline({ r }: { r: Rec }) {
  const hasRun2 = !!r.run2Status || (!!r.run2Action && r.run2Action !== "None");
  const hasRun3 = !!r.run3Status || (!!r.run3Action && r.run3Action !== "None");
  if (!hasRun2 && !hasRun3) return null;

  const statusCls = (s: string | null) =>
    s === "Broken" ? "neg" : s === "Weakening" ? "warn" : "pos";

  const run3Text =
    r.run3Action === "Exit"
      ? `sold${r.exitPrice != null ? " @ " + fmtPrice(r.exitPrice) : ""}`
      : r.run3Action === "Trim"
      ? `trimmed${r.exitPrice != null ? " @ " + fmtPrice(r.exitPrice) : ""}`
      : (r.run3Status ?? "checked").toLowerCase();

  return (
    <div className="intraday">
      <span className="intraday-label">Through the day</span>
      {hasRun2 && (
        <span className={`leg ${statusCls(r.run2Status)}`}>
          10 AM: {(r.run2Status ?? "checked").toLowerCase()}
          {r.run2Action === "Watch" ? " · watch" : ""}
        </span>
      )}
      {hasRun3 && (
        <span
          className={`leg ${
            r.run3Action === "Exit" || r.run3Action === "Trim"
              ? "neg"
              : statusCls(r.run3Status)
          }`}
        >
          3 PM: {run3Text}
        </span>
      )}
    </div>
  );
}

function StockRow({
  r,
  alloc,
  showWhy,
}: {
  r: Rec;
  alloc?: number;
  showWhy?: boolean;
}) {
  const move = typeof r.actualMove === "number" ? r.actualMove : null;
  const moveClass = move === null ? "" : move > 0 ? "pos" : move < 0 ? "neg" : "";
  const dir = r.expectedDirection ? DIR[r.expectedDirection] : null;
  return (
    <li className="stock-row col">
      <details className="srow">
        <summary className="srow-sum">
          <div className="stock-row-top">
            <div className="stock-main">
              <span className="ticker">{r.ticker ?? "—"}</span>
              {r.company && <span className="coname">{r.company}</span>}
            </div>
            <div className="stock-meta">
              {r.refPrice != null && (
                <span className="price">{fmtPrice(r.refPrice)}</span>
              )}
              {alloc != null && (
                <span className="alloc" title="How much of your money to put in this one">
                  {alloc}%
                </span>
              )}
              <span className="srow-chev" aria-hidden="true" />
            </div>
          </div>
          <div className="stock-sub">
            {dir && (
              <span className={`dir ${dir.cls}`}>
                {dir.arrow} {dir.text}
              </span>
            )}
            {typeof r.compositeScore === "number" && (
              <span className="conf">
                confidence {r.compositeScore.toFixed(0)}/100
              </span>
            )}
            {r.outcome && r.outcome !== "Pending" && (
              <span className={`outcome ${r.outcome === "Correct" ? "ok" : "bad"}`}>
                {r.outcome === "Correct" ? "✓ right" : "✗ wrong"}
              </span>
            )}
            {move !== null && (
              <span className={`move ${moveClass}`}>{signed(move)}</span>
            )}
          </div>
          {showWhy && r.why && <div className="why">{plainify(r.why)}</div>}
        </summary>
        <div className="srow-body">
          <StockDetail r={r} />
          <IntradayTimeline r={r} />
        </div>
      </details>
    </li>
  );
}

function YdayRow({ r }: { r: Rec }) {
  const move = typeof r.actualMove === "number" ? r.actualMove : null;
  return (
    <li className="stock-row col">
      <div className="stock-row-top">
        <div className="stock-main">
          <span className="ticker">{r.ticker ?? "—"}</span>
          <span
            className={`verdict ${
              r.verdict === "BUY" ? "buy" : r.verdict === "SELL" ? "sell" : "hold"
            }`}
          >
            {r.verdict ? VERDICT_WORD[r.verdict] ?? r.verdict : "—"}
          </span>
        </div>
        <div className="stock-meta">
          {r.outcome && (
            <span className={`outcome ${r.outcome === "Correct" ? "ok" : "bad"}`}>
              {r.outcome === "Correct" ? "✓ right" : "✗ wrong"}
            </span>
          )}
          {move !== null && (
            <span className={`move ${move > 0 ? "pos" : move < 0 ? "neg" : ""}`}>
              {signed(move)}
            </span>
          )}
        </div>
      </div>
      {r.why && <div className="why">{plainify(r.why)}</div>}
    </li>
  );
}

function Kpi({
  label,
  value,
  tone,
  hint,
}: {
  label: string;
  value: string;
  tone?: "pos" | "neg" | "neutral";
  hint?: ReactNode;
}) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className={`kpi-value ${tone ?? ""}`}>{value}</div>
      {hint && <div className="kpi-hint">{hint}</div>}
    </div>
  );
}

export default async function Page() {
  const d = await getDashboard();

  if (d.error) {
    return (
      <main className="container">
        <TopBar subtitle="Connection error" />
        <div className="card error-card">
          <strong>Couldn&apos;t reach Notion.</strong>
          <p>{d.error}</p>
          <p className="muted">
            Check NOTION_TOKEN and that the INVESTAI page is shared with the
            integration.
          </p>
        </div>
      </main>
    );
  }

  const { kpi } = d;
  const pnlTone =
    kpi.strategyPnl === null
      ? "neutral"
      : kpi.strategyPnl >= 0
      ? "pos"
      : "neg";

  const s = d.sentiment;
  // Gauge marker position: map index (-1..1) to 0..100%.
  const gaugePos = Math.round(((s.index + 1) / 2) * 100);

  // Conviction-weighted split across today's BUY basket.
  const buyAlloc = allocations(d.todayBuys);

  // Yesterday: only the standout hits and the worst misses, by move size.
  const gradedYday = d.yesterday.filter(
    (r) =>
      (r.outcome === "Correct" || r.outcome === "Wrong") &&
      typeof r.actualMove === "number"
  );
  const byMag = (a: Rec, b: Rec) =>
    Math.abs(b.actualMove as number) - Math.abs(a.actualMove as number);
  const yBest = gradedYday
    .filter((r) => r.outcome === "Correct")
    .sort(byMag)
    .slice(0, 3);
  const yWorst = gradedYday
    .filter((r) => r.outcome === "Wrong")
    .sort(byMag)
    .slice(0, 3);

  const weekend = isWeekendIST();

  return (
    <main className="container">
      <TopBar subtitle={`Showing ${fmtDate(d.latestDate)}`} />
      <TabNav active="home" />

      {weekend && (
        <div className="banner">
          <Moon size={16} className="banner-ico" />
          <span>
            The stock market is closed on weekends. You&apos;re looking at{" "}
            {fmtDate(d.latestDate)}&apos;s reading — fresh picks come back on
            Monday.
          </span>
        </div>
      )}

      {/* Market mood — surfaced at the very top so the day's overall read
          frames everything below it */}
      <Panel
        title={
          <>
            <Gauge className="ico" /> Today&apos;s market mood
          </>
        }
        hint={<span className={`sent-badge ${s.tone}`}>{s.label}</span>}
        className={`sentiment ${s.tone}`}
      >
        <div className="gauge">
          <div className="gauge-track" />
          <div className="gauge-marker" style={{ left: `${gaugePos}%` }} />
          <div className="gauge-labels">
            <span>Fearful</span>
            <span>Calm</span>
            <span>Greedy</span>
          </div>
        </div>
        <p className="sent-narrative">{s.narrative}</p>
        <p className="explain">
          Think of this like a mood meter. Left = people are scared and selling;
          right = people are excited and buying. The white dot is where today sits.
        </p>
        {s.agentNote && (
          <p className="sent-note">
            <span className="sent-note-label">In the model&apos;s words</span>{" "}
            {s.agentNote}
          </p>
        )}
      </Panel>

      {/* Error management — Daily Review fields that always existed in Notion
          but were never shown anywhere: what the model got wrong before and
          the standing rules it's applying today because of it. Placed BEFORE
          the calls themselves, on purpose — read this before trusting a
          BUY/SELL, not after. */}
      <Panel
        title={
          <>
            <AlertTriangle className="ico" /> Error management — check this first
          </>
        }
        hint={
          d.errorManagement.asOfDate
            ? `as of ${fmtDate(d.errorManagement.asOfDate)}`
            : undefined
        }
      >
        <p className="explain top">
          Before you act on today&apos;s calls, here&apos;s what the model has
          gotten wrong before and what it&apos;s watching out for now — so you
          know what to double-check yourself.
        </p>
        {d.errorManagement.correctableErrors.length > 0 && (
          <>
            <div className="yday-sub bad">Mistakes it could have avoided</div>
            <ul className="err-list">
              {d.errorManagement.correctableErrors.map((line, i) => (
                <li key={i}>{plainify(line)}</li>
              ))}
            </ul>
          </>
        )}
        {d.errorManagement.marketDrivenMisses.length > 0 && (
          <>
            <div className="yday-sub">
              Sound calls where the market just moved against it
            </div>
            <ul className="err-list muted-list">
              {d.errorManagement.marketDrivenMisses.map((line, i) => (
                <li key={i}>{plainify(line)}</li>
              ))}
            </ul>
          </>
        )}
        {d.errorManagement.standingLessons.length > 0 && (
          <>
            <div className="yday-sub ok">
              Rules it&apos;s applying today because of past mistakes
            </div>
            <ul className="err-list">
              {d.errorManagement.standingLessons.slice(0, 10).map((line, i) => (
                <li key={i}>{plainify(line)}</li>
              ))}
            </ul>
          </>
        )}
        {d.errorManagement.correctableErrors.length === 0 &&
          d.errorManagement.marketDrivenMisses.length === 0 &&
          d.errorManagement.standingLessons.length === 0 && (
            <p className="muted empty">No error notes recorded yet.</p>
          )}
      </Panel>

      {/* ============ TIER 1 — What to do today ============ */}
      <div className="group-eyebrow">Today&apos;s calls</div>

      {/* BUY — conviction-weighted allocation + why; open by default */}
      <Section
        title={
          <>
            <CircleArrowUp className="ico" /> Worth buying today
          </>
        }
        titleClass="buy"
        tone="buy"
        count={d.todayBuys.length}
        summary={tickerSummary(d.todayBuys) || "Nothing today"}
        hint={d.todayBuys.length > 1 ? "% = how to split your money" : undefined}
        defaultOpen
      >
        {d.todayBuys.length ? (
          <ul className="stock-list">
            {d.todayBuys.map((r, i) => (
              <StockRow
                key={i}
                r={r}
                alloc={d.todayBuys.length > 1 ? buyAlloc[i] : undefined}
                showWhy
              />
            ))}
          </ul>
        ) : (
          <p className="muted empty">No BUY calls for the latest day.</p>
        )}
      </Section>

      {/* SELL — with why; open by default */}
      <Section
        title={
          <>
            <CircleArrowDown className="ico" /> Avoid or sell today
          </>
        }
        titleClass="sell"
        tone="sell"
        count={d.todaySells.length}
        summary={tickerSummary(d.todaySells) || "Nothing today"}
        defaultOpen
      >
        {d.todaySells.length ? (
          <ul className="stock-list">
            {d.todaySells.map((r, i) => (
              <StockRow key={i} r={r} showWhy />
            ))}
          </ul>
        ) : (
          <p className="muted empty">No SELL calls for the latest day.</p>
        )}
      </Section>

      {/* HOLD — secondary; collapsed by default */}
      <Section
        title={
          <>
            <CircleMinus className="ico" /> Already own it? Just hold
          </>
        }
        titleClass="hold-h"
        tone="hold"
        count={d.todayHolds.length}
        summary={tickerSummary(d.todayHolds) || "Nothing today"}
      >
        {d.todayHolds.length ? (
          <ul className="stock-list">
            {d.todayHolds.map((r, i) => (
              <StockRow key={i} r={r} showWhy />
            ))}
          </ul>
        ) : (
          <p className="muted empty">No HOLD calls for the latest day.</p>
        )}
      </Section>

      {/* Looking up a specific stock (yesterday's call, its own track record,
          the coffee-shop debate) now lives on its own tab — see TabNav —
          instead of crowding the home page. */}

      {/* De-risk — Run 3 sold/trimmed before the 3:30 close */}
      {d.todayDerisk.length > 0 && (
        <Panel
          title={
            <>
              <Shield className="ico" /> Sold before the close
            </>
          }
          titleClass="sell"
        >
          <ul className="stock-list">
            {d.todayDerisk.map((r, i) => (
              <li className="stock-row col" key={i}>
                <div className="stock-row-top">
                  <div className="stock-main">
                    <span className="ticker">{r.ticker ?? "—"}</span>
                    <span className="verdict sell">
                      {r.run3Action === "Exit" ? "Sold" : "Trimmed"}
                    </span>
                  </div>
                  <div className="stock-meta">
                    {r.exitPrice != null && (
                      <span className="price">{fmtPrice(r.exitPrice)}</span>
                    )}
                  </div>
                </div>
                {r.run3Note && <div className="why">{plainify(r.run3Note)}</div>}
              </li>
            ))}
          </ul>
          <p className="explain">
            These were closed near 3 PM because the morning reason to hold them
            broke during the day — locking in the result before the market shut,
            so an overnight drop can&apos;t hurt.
          </p>
        </Panel>
      )}

      {/* ============ TIER 2 — How it's doing (glance) ============ */}
      <div className="group-eyebrow">How it&apos;s doing</div>

      <div className="kpi-hero">
        <div className="kpi-hero-top">
          <span className="kpi-label">Pretend profit so far</span>
          {kpi.correctStreak ? (
            <span className="kpi-streak">
              <Flame size={12} className="flame" /> {kpi.correctStreak}-day streak
            </span>
          ) : null}
        </div>
        <div className={`kpi-hero-val ${pnlTone}`}>{signed(kpi.strategyPnl)}</div>
        <div className="kpi-hint">
          compounded, equal-weight, if you&apos;d followed all {kpi.gradedCount}{" "}
          graded calls
        </div>
        {kpi.dataErrors > 0 ? (
          <div className="kpi-hint warn">
            ⚠ {kpi.dataErrors} call{kpi.dataErrors === 1 ? "" : "s"} ignored — a
            bad reference price was logged (needs a data fix, see report)
          </div>
        ) : null}
      </div>

      <section className="kpi-grid">
        <Kpi
          label="How often it's right"
          value={kpi.accuracy === null ? "—" : `${kpi.accuracy.toFixed(0)}%`}
          tone="neutral"
          hint={
            kpi.accuracy7d === null
              ? "50% is a coin-toss"
              : `last 7 days: ${kpi.accuracy7d.toFixed(0)}%`
          }
        />
        <Kpi
          label="Its report card"
          value={kpi.selfRating === null ? "—" : `${kpi.selfRating.toFixed(0)}/100`}
          tone="neutral"
          hint="the model grades itself"
        />
        <Kpi
          label="Most reliable stock"
          value={kpi.bestStock ? kpi.bestStock.ticker : "—"}
          tone="neutral"
          hint={
            kpi.bestStock
              ? `right ${kpi.bestStock.hitRate.toFixed(0)}% of ${kpi.bestStock.n} times`
              : undefined
          }
        />
        <Kpi
          label="Saved by selling early"
          value={kpi.mgmtAlpha === null ? "—" : signed(kpi.mgmtAlpha)}
          tone={
            kpi.mgmtAlpha === null
              ? "neutral"
              : kpi.mgmtAlpha >= 0
              ? "pos"
              : "neg"
          }
          hint="from the 3 PM de-risk check"
        />
      </section>

      {/* ============ TIER 3 — Context & track record ============ */}
      <div className="group-eyebrow">Context &amp; track record</div>

      {/* Gold & Silver */}
      <Panel
        title={
          <>
            <Coins className="ico" /> Gold &amp; Silver
          </>
        }
        hint="safe-haven options"
      >
        {d.commodities.length ? (
          <ul className="stock-list">
            {d.commodities.map((r, i) => {
              const meta = COMMODITY_META[r.ticker ?? ""] ?? {
                name: r.ticker ?? "—",
              };
              const dir = r.expectedDirection ? DIR[r.expectedDirection] : null;
              return (
                <li className="stock-row col" key={i}>
                  <div className="stock-row-top">
                    <div className="stock-main">
                      <Coins
                        size={20}
                        className={
                          r.ticker === "GOLDBEES" ? "coin-gold" : "coin-silver"
                        }
                      />
                      <span className="ticker">{meta.name}</span>
                      <span
                        className={`verdict ${
                          r.verdict === "BUY"
                            ? "buy"
                            : r.verdict === "SELL"
                            ? "sell"
                            : "hold"
                        }`}
                      >
                        {r.verdict ? VERDICT_WORD[r.verdict] ?? r.verdict : "—"}
                      </span>
                    </div>
                    <div className="stock-meta">
                      {r.refPrice != null && (
                        <span className="price">{fmtPrice(r.refPrice)}</span>
                      )}
                    </div>
                  </div>
                  <div className="stock-sub">
                    {dir && (
                      <span className={`dir ${dir.cls}`}>
                        {dir.arrow} {dir.text}
                      </span>
                    )}
                    {r.outcome && r.outcome !== "Pending" && (
                      <span
                        className={`outcome ${
                          r.outcome === "Correct" ? "ok" : "bad"
                        }`}
                      >
                        {r.outcome === "Correct" ? "✓ right" : "✗ wrong"}
                      </span>
                    )}
                    {typeof r.actualMove === "number" && (
                      <span
                        className={`move ${
                          r.actualMove > 0 ? "pos" : r.actualMove < 0 ? "neg" : ""
                        }`}
                      >
                        {signed(r.actualMove)}
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="muted empty">No Gold/Silver data for the latest day.</p>
        )}
      </Panel>

      {/* Beating the market? — is this actually adding value, or just riding
          Nifty up? A BUY that's "Correct" on a day the whole market rallied
          isn't real stock-picking skill. Uses the real Nifty 50 reading where
          it's been logged (from 2026-08-11 on), and falls back to GROWWN200
          (Nifty 200 ETF, already one of the 26 tracked names) on older days —
          see kpi.marketAlphaNiftyDays. Replaces the old self-grading accuracy
          line chart, which just restated the "how often it's right" KPI above
          as a graph without adding new signal. */}
      <Panel
        title={
          <>
            <Activity className="ico" /> Beating the market?
          </>
        }
        hint={
          kpi.marketAlphaDays > 0 ? `${kpi.marketAlphaDays} days compared` : undefined
        }
      >
        {kpi.marketAlpha === null ? (
          <p className="muted empty">Not enough graded days yet to compare.</p>
        ) : (
          <>
            <div className={`kpi-hero-val ${kpi.marketAlpha >= 0 ? "pos" : "neg"}`}>
              {signed(kpi.marketAlpha)}
            </div>
            <p className="explain">
              {kpi.marketAlpha >= 0 ? (
                <>
                  On the days it made a call, this model beat just holding the
                  overall market by <strong>{signed(kpi.marketAlpha)}</strong>.
                </>
              ) : (
                <>
                  On the days it made a call, this model did{" "}
                  <strong>{Math.abs(kpi.marketAlpha).toFixed(1)}% worse</strong> than
                  just holding the overall market. Being &quot;right&quot; on a
                  call isn&apos;t the same as beating the market — the market
                  can move further than the call did.
                </>
              )}
            </p>
            <p className="explain">
              {kpi.marketAlphaNiftyDays > 0
                ? kpi.marketAlphaNiftyDays === kpi.marketAlphaDays
                  ? "Compared against the real Nifty 50 index every day."
                  : `Compared against the real Nifty 50 on ${kpi.marketAlphaNiftyDays} of those days; the rest use a Nifty 200 fund (GROWWN200) as a stand-in, from before Nifty 50 was tracked.`
                : "Compared against a Nifty 200 fund (GROWWN200) as a stand-in for the market — the real Nifty 50 isn't logged yet."}
            </p>
          </>
        )}
      </Panel>

      {/* Track Record — 1yr backtest, told as a ₹100 story */}
      <Panel
        title={
          <>
            <TrendingUp className="ico" /> Does this actually work?
          </>
        }
        hint="1-year test"
      >
        <p className="explain top">
          Imagine you put <strong>₹100</strong> in one year ago and followed this
          plan every day. Here&apos;s where it would be today versus just leaving
          that ₹100 in the overall market.
        </p>
        <div className="money-grid">
          <div className="money-card win">
            <div className="money-label">Following this model</div>
            <div className="money-val pos">
              ₹{(100 * (1 + backtest.strategy_return_pct / 100)).toFixed(0)}
            </div>
            <div className="money-sub">
              {backtest.strategy_return_pct >= 0 ? "grew" : "shrank"} by{" "}
              {Math.abs(backtest.strategy_return_pct)}%
            </div>
          </div>
          <div className="money-card">
            <div className="money-label">The whole market (NIFTY 50)</div>
            <div
              className={`money-val ${
                backtest.benchmark_return_pct >= 0 ? "pos" : "neg"
              }`}
            >
              ₹{(100 * (1 + backtest.benchmark_return_pct / 100)).toFixed(0)}
            </div>
            <div className="money-sub">
              {backtest.benchmark_return_pct >= 0 ? "grew" : "shrank"} by{" "}
              {Math.abs(backtest.benchmark_return_pct)}%
            </div>
          </div>
        </div>
        <p className="money-headline">
          <TrendingUp size={15} className="mh-ico" /> It beat the market by about{" "}
          <strong>{Math.round(backtest.outperformance_pct)}%</strong> over the year.
        </p>
        <EquityChart data={backtest.equity_curve as any} />
        <div className="bt-legend">
          <span>
            <i className="dot strat" /> This model
          </span>
          <span>
            <i className="dot bench" /> Whole market
          </span>
        </div>
        <p className="bt-note">
          Reality check: this is a 1-year test of a simpler rule-based version, not
          the full AI you see above — so treat it as encouraging, not a promise. The
          worst dip along the way was {Math.abs(backtest.max_drawdown_pct)}% (your
          ₹100 briefly fell that much before recovering). Past results don&apos;t
          guarantee the future.
        </p>
      </Panel>

      {/* Yesterday — only the standout hits and worst misses */}
      <Panel
        title={
          <>
            <History className="ico" /> Yesterday&apos;s scorecard
          </>
        }
        hint={fmtDate(d.prevDate)}
      >
        {gradedYday.length ? (
          <>
            <div className="yday-sub ok">Worked well</div>
            {yBest.length ? (
              <ul className="stock-list">
                {yBest.map((r, i) => (
                  <YdayRow key={i} r={r} />
                ))}
              </ul>
            ) : (
              <p className="muted empty">No correct calls yesterday.</p>
            )}
            <div className="yday-sub bad">Missed</div>
            {yWorst.length ? (
              <ul className="stock-list">
                {yWorst.map((r, i) => (
                  <YdayRow key={i} r={r} />
                ))}
              </ul>
            ) : (
              <p className="muted empty">No wrong calls yesterday — clean sweep.</p>
            )}
          </>
        ) : (
          <p className="muted empty">
            Yesterday&apos;s calls are still being graded.
          </p>
        )}
      </Panel>

      <footer className="foot">
        Reads live from Notion · {fmtDate(d.latestDate)}
      </footer>
    </main>
  );
}
