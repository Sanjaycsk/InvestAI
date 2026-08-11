import { type Rec } from "@/lib/notion";
import { plainify } from "@/lib/plain";
import { sectorFor, SECTOR_LABEL } from "@/lib/sectors";
import OwnBadge from "./OwnBadge";
import { mlPredictionFor, CLASS_META, ML_HORIZON_DAYS } from "./MLTrend";

// The expanded "more details" view for one stock: what the model decided, how
// sure it was, and the plain-English reason behind each of the six factors it
// weighs. Presentational only (no state) so it works inside a server-rendered
// <details> row and inside the client "all stocks" browser alike.

const DIR: Record<string, { arrow: string; text: string; cls: string }> = {
  Up: { arrow: "▲", text: "expects it to go up", cls: "pos" },
  Down: { arrow: "▼", text: "expects it to go down", cls: "neg" },
  Flat: { arrow: "▬", text: "expects little change", cls: "" },
};

const VERDICT_WORD: Record<string, { word: string; cls: string }> = {
  BUY: { word: "Buy", cls: "pos" },
  SELL: { word: "Sell / avoid", cls: "neg" },
  HOLD: { word: "Hold", cls: "warn" },
};

function fmtPrice(n: number | null): string {
  if (n === null) return "—";
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export default function StockDetail({ r }: { r: Rec }) {
  const v = r.verdict ? VERDICT_WORD[r.verdict] : null;
  const dir = r.expectedDirection ? DIR[r.expectedDirection] : null;
  const conf = typeof r.compositeScore === "number" ? r.compositeScore : null;
  const sectorLabel = r.ticker ? SECTOR_LABEL[sectorFor(r.ticker)] : null;
  const ml = mlPredictionFor(r.ticker);
  const mlMeta = ml ? CLASS_META[ml.predicted_class] : null;

  return (
    <div className="sd">
      <div className="sd-top">
        {v && <span className={`sd-verdict ${v.cls}`}>{v.word}</span>}
        {r.category && <span className="sd-chip">{r.category}</span>}
        {sectorLabel && sectorLabel !== "Other" && (
          <span className="sd-chip">{sectorLabel}</span>
        )}
        {dir && (
          <span className={`sd-chip ${dir.cls}`}>
            {dir.arrow} {dir.text}
          </span>
        )}
      </div>

      {/* Personal action: everyone viewing this dashboard has a different
          real portfolio, so this turns the model's verdict into "what do I
          actually do", remembered on this device only. */}
      <OwnBadge ticker={r.ticker} verdict={r.verdict} />

      {/* A second, independent opinion: a traditional ML model's short-horizon
          lean, separate from the LLM's own (1-day) Expected Direction above.
          See MLTrend.tsx for the honest walk-forward accuracy caveat. */}
      {ml && mlMeta && (
        <div className="ml-chip">
          <span className="ml-chip-label">{ML_HORIZON_DAYS}-day ML lean</span>
          <span className={`dir ${mlMeta.cls}`}>
            {mlMeta.arrow} {mlMeta.text}
          </span>
          <span className="conf">{ml.confidence_pct}% sure</span>
        </div>
      )}

      <div className="sd-meta">
        {r.refPrice != null && (
          <span>
            Price when checked <b>{fmtPrice(r.refPrice)}</b>
          </span>
        )}
        {conf != null && (
          <span className="sd-conf" title="How sure the model is, out of 100">
            <span className="sd-conf-bar" aria-hidden="true">
              <span className="sd-conf-fill" style={{ width: `${Math.max(0, Math.min(100, conf))}%` }} />
            </span>
            {conf}/100 sure
          </span>
        )}
      </div>

      {r.factors.length > 0 ? (
        <ul className="sd-factors">
          {r.factors.map((f, i) => (
            <li key={i}>
              <span className="sd-flabel">{f.label}</span>
              <span className="sd-ftext">{plainify(f.text)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="sd-empty">No detailed notes recorded for this one.</p>
      )}
    </div>
  );
}
