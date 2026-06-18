// Dependency-free SVG line chart for accuracy over time.
// Server component — pure rendering, no client JS needed.

type Point = { date: string | null; accuracy: number | null };

export default function AccuracyChart({ data }: { data: Point[] }) {
  const points = data
    .filter((d) => typeof d.accuracy === "number")
    .map((d) => ({ date: d.date, y: d.accuracy as number }));

  if (points.length < 2) {
    return (
      <div className="chart-empty">
        Not enough graded days yet — the line appears once there are 2+ reviews.
      </div>
    );
  }

  const W = 320;
  const H = 120;
  const padL = 28;
  const padR = 8;
  const padT = 10;
  const padB = 18;

  const n = points.length;
  const ys = points.map((p) => p.y);
  const minY = Math.min(40, Math.floor(Math.min(...ys) / 10) * 10);
  const maxY = Math.max(100, Math.ceil(Math.max(...ys) / 10) * 10);

  const x = (i: number) =>
    padL + (i / (n - 1)) * (W - padL - padR);
  const y = (v: number) =>
    padT + (1 - (v - minY) / (maxY - minY)) * (H - padT - padB);

  const line = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.y).toFixed(1)}`)
    .join(" ");

  const area =
    `M${x(0).toFixed(1)},${y(points[0].y).toFixed(1)} ` +
    points.map((p, i) => `L${x(i).toFixed(1)},${y(p.y).toFixed(1)}`).join(" ") +
    ` L${x(n - 1).toFixed(1)},${(H - padB).toFixed(1)} L${x(0).toFixed(1)},${(
      H - padB
    ).toFixed(1)} Z`;

  const gridVals = [minY, Math.round((minY + maxY) / 2), maxY];

  const last = points[points.length - 1];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      role="img"
      aria-label="Accuracy over time"
      className="chart-svg"
    >
      {gridVals.map((g) => (
        <g key={g}>
          <line
            x1={padL}
            x2={W - padR}
            y1={y(g)}
            y2={y(g)}
            className="chart-grid"
          />
          <text x={2} y={y(g) + 3} className="chart-axis">
            {g}
          </text>
        </g>
      ))}
      <path d={area} className="chart-area" />
      <path d={line} className="chart-line" />
      {points.map((p, i) => (
        <circle key={i} cx={x(i)} cy={y(p.y)} r={i === n - 1 ? 3.5 : 2} className="chart-dot" />
      ))}
      <text x={x(n - 1)} y={y(last.y) - 6} textAnchor="end" className="chart-last">
        {last.y.toFixed(0)}%
      </text>
    </svg>
  );
}
