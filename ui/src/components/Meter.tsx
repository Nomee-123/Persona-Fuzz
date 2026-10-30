export function Meter({ value, tone = "accent", label }: { value: number; tone?: "accent" | "bad" | "good" | "warn"; label?: string }) {
  const clamped = Math.max(0, Math.min(1, value));
  return (
    <div className="meter" title={label ?? `${(clamped * 100).toFixed(1)}%`}>
      <div className={`meter-fill meter-${tone}`} style={{ width: `${clamped * 100}%` }} />
    </div>
  );
}
