interface Series {
  name: string;
  color: string;
  values: number[];
}

export function LineChart({
  series,
  labels,
  height = 230,
  yLabel,
  compact = false,
}: {
  series: Series[];
  labels: string[];
  height?: number;
  yLabel?: string;
  compact?: boolean;
}) {
  const width = 640;
  const pad = { left: 42, right: 18, top: 16, bottom: 32 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const points = Math.max(1, ...series.map((s) => s.values.length));
  const x = (i: number) => pad.left + (points === 1 ? innerW / 2 : (i / (points - 1)) * innerW);
  const y = (v: number) => pad.top + innerH - Math.max(0, Math.min(1, v)) * innerH;
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div className={`chart ${compact ? "chart-compact" : ""}`}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="CEGIS convergence chart">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={width - pad.right} y1={y(t)} y2={y(t)} className="grid" />
            <text x={pad.left - 8} y={y(t) + 4} textAnchor="end" className="axis">
              {Math.round(t * 100)}%
            </text>
          </g>
        ))}
        {yLabel ? (
          <text x={pad.left} y={10} className="axis" textAnchor="start">
            {yLabel}
          </text>
        ) : null}
        {labels.map((label, i) => (
          <text key={`${label}-${i}`} x={x(i)} y={height - 8} textAnchor="middle" className="axis">
            {label}
          </text>
        ))}
        {series.map((s) => {
          const d = s.values
            .map((v, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(2)} ${y(v).toFixed(2)}`)
            .join(" ");
          return (
            <g key={s.name}>
              <path d={d} fill="none" stroke={s.color} strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" />
              {s.values.map((v, i) => (
                <circle key={i} cx={x(i)} cy={y(v)} r={3.3} fill={s.color}>
                  <title>{`${s.name} · ${labels[i] ?? i + 1}: ${(v * 100).toFixed(1)}%`}</title>
                </circle>
              ))}
            </g>
          );
        })}
      </svg>
      <div className="legend">
        {series.map((s) => (
          <span key={s.name}>
            <i style={{ background: s.color }} /> {s.name}
          </span>
        ))}
      </div>
    </div>
  );
}
