import type { ReactNode } from "react";

export function Stat({
  label,
  value,
  detail,
  tone = "default",
  children,
}: {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  tone?: "default" | "good" | "warn" | "bad";
  children?: ReactNode;
}) {
  return (
    <div className={`stat stat-${tone}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {detail ? <div className="stat-detail">{detail}</div> : null}
      {children}
    </div>
  );
}
