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
  return (
    <li className="stock-row col">
      <div className="stock-row-top">
        <div className="stock-main">
          <span className="ticker">{r.ticker ?? "—"}</span>
          {r.category && <span className="chip">{r.category}</span>}
        </div>
        <div className="stock-meta">
          {alloc != null && <span className="alloc">{alloc}%</span>}
          {typeof r.compositeScore === "number" && (
            <span className="score">{r.compositeScore.toFixed(0)}</span>
          )}
          {r.outcome && r.outcome !== "Pending" && (
            <span className={`outcome ${r.outcome === "Correct" ? "ok" : "bad"}`}>
              {r.outcome === "Correct" ? "✓" : "✗"}
            </span>
          )}
          {move !== null && (
            <span className={`move ${moveClass}`}>{signed(move)}</span>
          )}
        </div>
      </div>
      {showWhy && r.why && <div className="why">{r.why}</div>}
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
            {r.verdict ?? "—"}
          </span>
        </div>
        <div className="stock-meta">
          {r.outcome && (
            <span className={`outcome ${r.outcome === "Correct" ? "ok" : "bad"}`}>
              {r.outcome === "Correct" ? "✓" : "✗"}
            </span>
          )}
          {move !== null && (
            <span className={`move ${move > 0 ? "pos" : move < 0 ? "neg" : ""}`}>
              {signed(move)}
            </span>
          )}
        </div>
      </div>
      {r.why && <div className="why">{r.why}</div>}
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

  return (
    <main className="container">
      <TopBar subtitle={`Latest: ${fmtDate(d.latestDate)}`} />

      {/* Market sentiment */}
      <section className={`card sentiment ${s.tone}`}>
        <div className="card-head">
          <h2>Market sentiment today</h2>
          <span className={`sent-badge ${s.tone}`}>{s.label}</span>
        </div>
        <div className="gauge">
          <div className="gauge-track" />
          <div className="gauge-marker" style={{ left: `${gaugePos}%` }} />
          <div className="gauge-labels">
            <span>Crash</span>
            <span>Neutral</span>
            <span>Euphoric</span>
          </div>
        </div>
        <p className="sent-narrative">{s.narrative}</p>
        {s.agentNote && (
          <p className="sent-note">
            <span className="sent-note-label">Agent note</span> {s.agentNote}
          </p>
        )}
      </section>

      {/* Gold & Silver */}
      <section className="card">
        <div className="card-head">
          <h2>Gold &amp; Silver</h2>
          <span className="muted">commodities</span>
        </div>
        {d.commodities.length ? (
          <ul className="stock-list">
            {d.commodities.map((r, i) => {
              const meta = COMMODITY_META[r.ticker ?? ""] ?? {
                name: r.ticker ?? "—",
                icon: "•",
              };
              return (
                <li className="stock-row commodity-row" key={i}>
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
                      {r.verdict ?? "—"}
                    </span>
                  </div>
                  <div className="stock-meta">
                    {typeof r.compositeScore === "number" && (
                      <span className="score">{r.compositeScore.toFixed(0)}</span>
                    )}
                    {r.outcome && r.outcome !== "Pending" && (
                      <span
                        className={`outcome ${
                          r.outcome === "Correct" ? "ok" : "bad"
                        }`}
                      >
                        {r.outcome === "Correct" ? "✓" : "✗"}
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

      {/* KPI strip */}
      <section className="kpi-grid">
        <Kpi
          label="Strategy P&L (paper)"
          value={signed(kpi.strategyPnl)}
          tone={pnlTone as any}
          hint={`${kpi.gradedCount} graded calls`}
        />
        <Kpi
          label="Accuracy (latest)"
          value={kpi.accuracy === null ? "—" : `${kpi.accuracy.toFixed(0)}%`}
          tone="neutral"
          hint={
            kpi.accuracy7d === null
              ? undefined
              : `7-day avg ${kpi.accuracy7d.toFixed(0)}%`
          }
        />
        <Kpi
          label="Self-rating"
          value={kpi.selfRating === null ? "—" : `${kpi.selfRating.toFixed(0)}`}
          tone="neutral"
          hint={kpi.correctStreak ? `🔥 ${kpi.correctStreak}-day streak` : undefined}
        />
        <Kpi
          label="Best read"
          value={kpi.bestStock ? kpi.bestStock.ticker : "—"}
          tone="neutral"
          hint={
            kpi.bestStock
              ? `${kpi.bestStock.hitRate.toFixed(0)}% of ${kpi.bestStock.n}`
              : undefined
          }
        />
      </section>

      {/* Accuracy chart */}
      <section className="card">
        <div className="card-head">
          <h2>Accuracy trend</h2>
          <span className="muted">{d.reviews.length} days</span>
        </div>
        <AccuracyChart
          data={d.reviews.map((r) => ({ date: r.date, accuracy: r.accuracy }))}
        />
      </section>

      {/* Track Record — 1yr backtest */}
      <section className="card">
        <div className="card-head">
          <h2>Track record · {backtest.lookback} backtest</h2>
          <span className="muted">{backtest.n_calls} calls</span>
        </div>
        <div className="bt-grid">
          <div className="bt-stat">
            <div className="bt-label">Strategy</div>
            <div className={`bt-val ${backtest.strategy_return_pct >= 0 ? "pos" : "neg"}`}>
              {backtest.strategy_return_pct >= 0 ? "+" : ""}
              {backtest.strategy_return_pct}%
            </div>
          </div>
          <div className="bt-stat">
            <div className="bt-label">NIFTY 50</div>
            <div className={`bt-val ${backtest.benchmark_return_pct >= 0 ? "pos" : "neg"}`}>
              {backtest.benchmark_return_pct >= 0 ? "+" : ""}
              {backtest.benchmark_return_pct}%
            </div>
          </div>
          <div className="bt-stat">
            <div className="bt-label">Alpha</div>
            <div className={`bt-val ${backtest.outperformance_pct >= 0 ? "pos" : "neg"}`}>
              {backtest.outperformance_pct >= 0 ? "+" : ""}
              {backtest.outperformance_pct}%
            </div>
          </div>
        </div>
        <EquityChart data={backtest.equity_curve as any} />
        <div className="bt-legend">
          <span><i className="dot strat" /> Strategy</span>
          <span><i className="dot bench" /> NIFTY 50</span>
          <span className="muted">
            acc {backtest.accuracy_pct}% · max DD {backtest.max_drawdown_pct}%
          </span>
        </div>
        <p className="bt-note">
          Technical-baseline backtest (trend + RSI), graded like the live agent &
          benchmarked vs NIFTY buy-and-hold. Not a replay of the LLM agent; no
          costs/slippage. {backtest.period.start} → {backtest.period.end}.
        </p>
      </section>

      {/* Today BUY — with conviction-weighted allocation + why */}
      <section className="card">
        <div className="card-head">
          <h2 className="buy">🟢 Buy today</h2>
          <span className="muted">
            {d.todayBuys.length > 1 ? "% = suggested split" : d.todayBuys.length}
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
          <h2 className="sell">🔴 Sell / avoid today</h2>
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
          <h2 className="hold-h">🟡 Hold — if you own it, sit tight</h2>
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
