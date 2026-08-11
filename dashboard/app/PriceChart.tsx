// Dependency-free SVG line chart: one stock's price over time, plus two
// trend lines computed from the same readings — a short-term average (reacts
// fast) and a longer-term average (reacts slow). Short above long = the
// recent trend is leaning up (bullish); short below long = leaning down
// (bearish). No new data source: this is built entirely from the Ref Price
// already logged on every Recommendations row for this ticker.
// Server component — pure rendering, no client JS needed.

type Point = { date: string; refPrice: number };

const SHORT_WINDOW = 3;
const LONG_WINDOW = 8;

function trailingAvg(vals: number[], i: number, window: number): number {
  const start = Math.max(0, i - window + 1);
  const slice = vals.slice(start, i + 1);
  return slice.reduce((a, b) => a + b, 0) / slice.length;
}

function fmtShortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export default function PriceChart({ data }: { data: Point[] }) {
  if (data.length < 3) {
    return (
      <div className="chart-empty">
        Not enough daily readings yet for this stock — the chart appears once
        there are 3+.
      </div>
    );
  }

  const prices = data.map((d) => d.refPrice);
  const shortAvg = prices.map((_, i) => trailingAvg(prices, i, SHORT_WINDOW));
  const longAvg = prices.map((_, i) => trailingAvg(prices, i, LONG_WINDOW));

  const W = 320;
  const H = 130;
  const padL = 44;
  const padR = 8;
  const padT = 10;
  const padB = 18;

  const n = data.length;
  const allVals = [...prices, ...shortAvg, ...longAvg];
  const minY = Math.min(...allVals);
  const maxY = Math.max(...allVals);
  const span = maxY - minY || 1;

  const x = (i: number) => padL + (i / (n - 1)) * (W - padL - padR);
  const y = (v: number) => padT + (1 - (v - minY) / span) * (H - padT - padB);

  const linePath = (vals: number[]) =>
    vals.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");

  const gridVals = [minY, (minY + maxY) / 2, maxY];
  const lastShort = shortAvg[shortAvg.length - 1];
  const lastLong = longAvg[longAvg.length - 1];
  const trendingUp = lastShort >= lastLong;

  return (
    <div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        role="img"
        aria-label="Price over time"
        className="chart-svg"
      >
        {gridVals.map((g, i) => (
          <g key={i}>
            <line x1={padL} x2={W - padR} y1={y(g)} y2={y(g)} className="chart-grid" />
            <text x={2} y={y(g) + 3} className="chart-axis">
              {"₹" + g.toFixed(0)}
            </text>
          </g>
        ))}
        <path d={linePath(longAvg)} className="chart-line-long" />
        <path d={linePath(shortAvg)} className="chart-line-short" />
        <path d={linePath(prices)} className="chart-line" />
        <circle
          cx={x(n - 1)}
          cy={y(prices[n - 1])}
          r={3.5}
          className="chart-dot"
        />
        <text x={x(0)} y={H - 3} className="chart-axis">
          {fmtShortDate(data[0].date)}
        </text>
        <text x={x(n - 1)} y={H - 3} textAnchor="end" className="chart-axis">
          {fmtShortDate(data[n - 1].date)}
        </text>
      </svg>
      <div className="chart-legend">
        <span><i className="dot strat" /> Price</span>
        <span><i className="dot short" /> Recent trend</span>
        <span><i className="dot long" /> Longer trend</span>
      </div>
      <p className="explain">
        {trendingUp ? (
          <>The recent trend line is <strong>above</strong> the longer one — leaning bullish (up).</>
        ) : (
          <>The recent trend line is <strong>below</strong> the longer one — leaning bearish (down).</>
        )}{" "}
        This is just the price history, not a prediction — always check today&apos;s
        actual call above.
      </p>
    </div>
  );
}
