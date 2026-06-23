import { getDashboard, type Rec } from "@/lib/notion";
import AccuracyChart from "./AccuracyChart";
import EquityChart from "./EquityChart";
import TopBar from "./TopBar";
import backtest from "@/data/backtest.json";

// Always render fresh from Notion.
export const dynamic = "force-dynamic";
export const revalidate = 0;

const COMMODITY_META: Record<string, { name: string; icon: string }> = {
  GOLDBEES: { name: "Gold (GOLDBEES)", icon: "🥇" },
  SILVERBEES: { name: "Silver (SILVERBEES)", icon: "🥈" },
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

// Plain-English read of the model's expected direction for the day.
const DIR: Record<string, { arrow: string; text: string; cls: string }> = {
  Up: { arrow: "▲", text: "expects it to go up", cls: "pos" },
  Down: { arrow: "▼", text: "expects it to go down", cls: "neg" },
  Flat: { arrow: "▬", text: "expects little change", cls: "" },
};

// Swap the most common market jargon in the model's one-liner for words
// a non-finance reader understands. Conservative, whole-word only.
const GLOSSARY: [RegExp, string][] = [
  [/\b200-?DMA\b/gi, "its long-term average price"],
  [/\b50-?DMA\b/gi, "its average price"],
  [/\bDMA\b/gi, "average price"],
  [/\bMACD\b/gi, "the trend signal"],
  [/\bRSI\b/gi, "momentum"],
  [/\bP\/E\b/gi, "the price-vs-profit ratio"],
  [/\bbullish\b/gi, "positive"],
  [/\bbearish\b/gi, "negative"],
  [/\boverbought\b/gi, "looking expensive"],
  [/\boversold\b/gi, "looking cheap"],
  [/\bbreakout\b/gi, "a sharp move up"],
  [/\bresistance\b/gi, "a price ceiling"],
  [/\bsupport\b/gi, "a price floor"],
];
function plainify(s: string | null): string | null {
  if (!s) return s;
  let out = s;
  for (const [re, rep] of GLOSSARY) out = out.replace(re, rep);
  return out;
}

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
      <IntradayTimeline r={r} />
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
  hint?: string;
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

      {weekend && (
        <div className="banner">
          🛌 The stock market is closed on weekends. You&apos;re looking at{" "}
          {fmtDate(d.latestDate)}&apos;s reading — fresh picks come back on Monday.
        </div>
      )}

      {/* Market mood */}
      <section className={`card sentiment ${s.tone}`}>
        <div className="card-head">
          <h2>Today&apos;s market mood</h2>
          <span className={`sent-badge ${s.tone}`}>{s.label}</span>
        </div>
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
      </section>

      {/* Gold & Silver */}
      <section className="card">
        <div className="card-head">
          <h2>Gold &amp; Silver</h2>
          <span className="muted">safe-haven options</span>
        </div>
        {d.commodities.length ? (
          <ul className="stock-list">
            {d.commodities.map((r, i) => {
              const meta = COMMODITY_META[r.ticker ?? ""] ?? {
                name: r.ticker ?? "—",
                icon: "•",
              };
              const dir = r.expectedDirection ? DIR[r.expectedDirection] : null;
              return (
                <li className="stock-row col" key={i}>
                  <div className="stock-row-top">
                    <div className="stock-main">
                      <span className="commodity-icon">{meta.icon}</span>
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
      </section>

      {/* KPI strip — plain-English scorecards */}
      <section className="kpi-grid">
        <Kpi
          label="Pretend profit so far"
          value={signed(kpi.strategyPnl)}
          tone={pnlTone as any}
          hint={`if you'd followed all ${kpi.gradedCount} graded calls`}
        />
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
          hint={
            kpi.correctStreak
              ? `🔥 ${kpi.correctStreak} good days in a row`
              : "the model grades itself"
          }
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

      {/* Accuracy chart */}
      <section className="card">
        <div className="card-head">
          <h2>How often it&apos;s been right</h2>
          <span className="muted">last {d.reviews.length} days</span>
        </div>
        <AccuracyChart
          data={d.reviews.map((r) => ({ date: r.date, accuracy: r.accuracy }))}
        />
        <p className="explain">
          Each point is one day&apos;s score. Higher is better. 50% is the same as
          flipping a coin — above that line means the model is doing better than luck.
        </p>
      </section>

      {/* Track Record — 1yr backtest, told as a ₹100 story */}
      <section className="card">
        <div className="card-head">
          <h2>Does this actually work?</h2>
          <span className="muted">1-year test</span>
        </div>
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
          👉 It beat the market by about{" "}
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
      </section>

      {/* Today BUY — with conviction-weighted allocation + why */}
      <section className="card">
        <div className="card-head">
          <h2 className="buy">🟢 Worth buying today</h2>
          <span className="muted">
            {d.todayBuys.length > 1 ? "% = how to split your money" : d.todayBuys.length}
          </span>
        </div>
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
      </section>

      {/* Today SELL — with why */}
      <section className="card">
        <div className="card-head">
          <h2 className="sell">🔴 Avoid or sell today</h2>
          <span className="muted">{d.todaySells.length}</span>
        </div>
        {d.todaySells.length ? (
          <ul className="stock-list">
            {d.todaySells.map((r, i) => (
              <StockRow key={i} r={r} showWhy />
            ))}
          </ul>
        ) : (
          <p className="muted empty">No SELL calls for the latest day.</p>
        )}
      </section>

      {/* Today HOLD — already own it? sit tight */}
      <section className="card">
        <div className="card-head">
          <h2 className="hold-h">🟡 Already own it? Just hold</h2>
          <span className="muted">{d.todayHolds.length}</span>
        </div>
        {d.todayHolds.length ? (
          <ul className="stock-list">
            {d.todayHolds.map((r, i) => (
              <StockRow key={i} r={r} showWhy />
            ))}
          </ul>
        ) : (
          <p className="muted empty">No HOLD calls for the latest day.</p>
        )}
      </section>

      {/* Today's de-risk — Run 3 sold/trimmed before the 3:30 close */}
      {d.todayDerisk.length > 0 && (
        <section className="card">
          <div className="card-head">
            <h2 className="sell">🛡️ Sold before the close</h2>
            <span className="muted">3 PM de-risk</span>
          </div>
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
            broke during the day — locking in the result before the market shut, so
            an overnight drop can&apos;t hurt.
          </p>
        </section>
      )}

      {/* Yesterday — only the standout hits and worst misses */}
      <section className="card">
        <div className="card-head">
          <h2>Yesterday&apos;s scorecard</h2>
          <span className="muted">{fmtDate(d.prevDate)}</span>
        </div>
        {gradedYday.length ? (
          <>
            <div className="yday-sub ok">✅ Worked well</div>
            {yBest.length ? (
              <ul className="stock-list">
                {yBest.map((r, i) => (
                  <YdayRow key={i} r={r} />
                ))}
              </ul>
            ) : (
              <p className="muted empty">No correct calls yesterday.</p>
            )}
            <div className="yday-sub bad">❌ Missed</div>
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
      </section>

      <footer className="foot">
        Reads live from Notion · {fmtDate(d.latestDate)}
      </footer>
    </main>
  );
}
