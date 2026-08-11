import { type Rec, getDashboard } from "@/lib/notion";
import { plainify } from "@/lib/plain";
import TopBar from "../TopBar";
import TabNav from "../TabNav";
import StockLookup from "../StockLookup";
import DateFilter from "../DateFilter";
import { AlertTriangle, History, Clock } from "../Icons";

// Always render fresh from Notion.
export const dynamic = "force-dynamic";
export const revalidate = 0;

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

function signed(n: number | null): string {
  if (n === null) return "—";
  const s = n > 0 ? "+" : "";
  return `${s}${n.toFixed(1)}%`;
}

const VERDICT_WORD: Record<string, string> = {
  BUY: "Buy",
  SELL: "Sell / avoid",
  HOLD: "Hold",
};

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

export default async function LookupPage() {
  const d = await getDashboard();

  if (d.error) {
    return (
      <main className="container">
        <TopBar subtitle="Connection error" />
        <div className="card error-card">
          <strong>Couldn&apos;t reach Notion.</strong>
          <p>{d.error}</p>
        </div>
      </main>
    );
  }

  // Yesterday: only the standout hits and the worst misses, by move size —
  // across ALL stocks (this is a whole-portfolio recap, not per-stock; the
  // stock picker above already covers "how did THIS one do yesterday").
  const gradedYday = d.yesterday.filter(
    (r) =>
      (r.outcome === "Correct" || r.outcome === "Wrong") &&
      typeof r.actualMove === "number"
  );
  const byMag = (a: Rec, b: Rec) =>
    Math.abs((b.actualMove as number)) - Math.abs((a.actualMove as number));
  const yBest = gradedYday.filter((r) => r.outcome === "Correct").sort(byMag).slice(0, 3);
  const yWorst = gradedYday.filter((r) => r.outcome === "Wrong").sort(byMag).slice(0, 3);

  return (
    <main className="container">
      <TopBar subtitle="Details" />
      <TabNav active="lookup" />

      <p className="explain top">
        Pick any of the watchlist names to see today&apos;s call, how
        yesterday&apos;s call went, this stock&apos;s own track record, a
        price chart, and what different kinds of investors would do.
      </p>

      <section className="card allstocks-card">
        <StockLookup
          stocks={d.today}
          yesterday={d.yesterday}
          tickerStats={d.tickerStats}
          trackRecordDays={d.trackRecordDays}
          coffee={d.coffee}
          priceHistory={d.priceHistory}
        />
      </section>

      {/* Browse a past day — capped at the last 7 trading days on purpose;
          this is a quick recent-history check, not a full archive (the
          1-year backtest further down covers the long view). */}
      <div className="group-eyebrow">Past week</div>
      <section className="card">
        <div className="card-head">
          <h2>
            <Clock className="ico" /> Browse a past day
          </h2>
        </div>
        <DateFilter days={d.recentDays} />
      </section>

      {/* Error management — a GENERAL summary of the kind of mistakes this
          model tends to make (the standing Lessons rule set), not something
          tied to yesterday or to one stock. Yesterday's specific notes are
          shown separately below, clearly dated, so the two aren't confused. */}
      <div className="group-eyebrow">Before you trust it</div>
      <section className="card">
        <div className="card-head">
          <h2>
            <AlertTriangle className="ico" /> Common mistakes this model makes
          </h2>
        </div>
        <p className="explain top">
          This is a running list of the kind of errors the model has made
          before and corrects for now — general patterns, not anything about
          one stock or one day. Worth a skim before you trust a call.
        </p>
        {d.errorManagement.standingLessons.length > 0 ? (
          <ul className="err-list">
            {d.errorManagement.standingLessons.map((line, i) => (
              <li key={i}>{plainify(line)}</li>
            ))}
          </ul>
        ) : (
          <p className="muted empty">No standing rules recorded yet.</p>
        )}

        {(d.errorManagement.correctableErrors.length > 0 ||
          d.errorManagement.marketDrivenMisses.length > 0) && (
          <details className="cns-legend">
            <summary>
              Specifically from{" "}
              {d.errorManagement.asOfDate ? fmtDate(d.errorManagement.asOfDate) : "yesterday"}
            </summary>
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
                <div className="yday-sub">Sound calls where the market just moved against it</div>
                <ul className="err-list muted-list">
                  {d.errorManagement.marketDrivenMisses.map((line, i) => (
                    <li key={i}>{plainify(line)}</li>
                  ))}
                </ul>
              </>
            )}
          </details>
        )}
      </section>

      {/* Yesterday's scorecard — moved off the home page; a whole-portfolio
          recap, not specific to one stock. */}
      <section className="card">
        <div className="card-head">
          <h2>
            <History className="ico" /> Yesterday&apos;s scorecard
          </h2>
          <span className="muted">{fmtDate(d.prevDate)}</span>
        </div>
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
          <p className="muted empty">Yesterday&apos;s calls are still being graded.</p>
        )}
      </section>

      {/* How this all works — reference material, collapsed by default so it
          doesn't get in the way of actually looking a stock up. */}
      <div className="group-eyebrow">How InvestAI works</div>
      <details className="card cns-legend">
        <summary>How to read a stock&apos;s call</summary>
        <div className="key-block">
          <div className="key-h">The basics</div>
          <p className="explain top">
            Every trading morning, the model checks 26 things — 23 stocks, one
            broad-market fund, and gold + silver — and gives each one a call:
            <strong> Buy</strong>, <strong>Hold</strong>, or{" "}
            <strong>Sell / avoid</strong>. That morning call is
            &quot;frozen&quot; for the day — two lighter checks later (around
            10 AM and 3 PM) only watch for the reasoning breaking down; they
            never change the call itself.
          </p>
        </div>
        <div className="key-block">
          <div className="key-h">The confidence score</div>
          <p className="explain top">
            Each stock gets a score out of 100, built from six things: how
            healthy the business is, its price trend, whether it&apos;s cheap
            or pricey, the big-picture economy, what people are saying about
            it, and what could go wrong. Higher isn&apos;t always
            better — the model has found its 60-70 &quot;Watchlist&quot; band
            has actually been more reliable than its rare 80+
            &quot;Strong Buy&quot; calls, so treat a very high score as a cue
            to double-check, not extra certainty.
          </p>
        </div>
        <div className="key-block">
          <div className="key-h">Grading itself</div>
          <p className="explain top">
            Every morning, before making new calls, the model checks
            yesterday&apos;s: did the stock actually move the way it said it
            would? That becomes the accuracy number you see on the Today tab.
            It also keeps a running list of its own mistakes (see above) and
            is supposed to apply those lessons going forward.
          </p>
        </div>
        <div className="key-block">
          <div className="key-h">What it isn&apos;t</div>
          <p className="explain top">
            This is research and education only — it never places a real
            trade. The &quot;profit&quot; numbers on the Today tab are
            pretend: what you&apos;d have made if you&apos;d actually followed
            every call. Markets are uncertain and past results don&apos;t
            guarantee anything — always make your own call before you invest
            real money.
          </p>
        </div>
      </details>

      <footer className="foot">Reads live from Notion</footer>
    </main>
  );
}
