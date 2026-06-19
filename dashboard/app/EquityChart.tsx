// Dual-line equity curve: strategy vs benchmark. Dependency-free SVG.

type Pt = { date: string; strategy: number; benchmark: number | null };

export default function EquityChart({ data }: { data: Pt[] }) {
  const pts = data.filter((d) => typeof d.strategy === "number");
  if (pts.length < 2) {
    return <div className="chart-empty">Not enough data.</div>;
  }

  const W = 320,
    H = 130,
    padL = 30,
    padR = 8,
    padT = 10,
    padB = 18;
  const n = pts.length;

  const vals: number[] = [];
  pts.forEach((p) => {
    vals.push(p.strategy);
    if (typeof p.benchmark === "number") vals.push(p.benchmark);
  });
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const pad = (hi - lo) * 0.08 || 0.05;
  const minY = lo - pad;
  const maxY = hi + pad;

  const x = (i: number) => padL + (i / (n - 1)) * (W - padL - padR);
  const y = (v: number) =>
    padT + (1 - (v - minY) / (maxY - minY)) * (H - padT - padB);

  const path = (key: "strategy" | "benchmark") => {
    let d = "";
    let started = false;
    pts.forEach((p, i) => {
      const v = p[key];
      if (typeof v !== "number") return;
      d += `${started ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)} `;
      started = true;
    });
    return d.trim();
  };

  // y gridlines as % return from 1.0 baseline
  const pct = (v: number) => `${v >= 1 ? "+" : ""}${Math.round((v - 1) * 100)}%`;
  const grid = [minY, 1, maxY];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" className="chart-svg" role="img" aria-label="Backtest equity curve">
      {grid.map((g, i) => (
        <g key={i}>
          <line x1={padL} x2={W - padR} y1={y(g)} y2={y(g)} className="chart-grid" />
          <text x={2} y={y(g) + 3} className="chart-axis">{pct(g)}</text>
        </g>
      ))}
      <path d={path("benchmark")} className="eq-bench" />
      <path d={path("strategy")} className="eq-strat" />
    </svg>
  );
}
