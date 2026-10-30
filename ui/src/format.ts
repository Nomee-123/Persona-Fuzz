export function pct(value: number | undefined, digits = 0): string {
  if (value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function num(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-IN").format(value);
}

export function bytes(value: number | undefined): string {
  if (value === undefined) return "—";
  if (value < 1024) return `${Math.round(value)} B`;
  return `${(value / 1024).toFixed(1)} KB`;
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat("en-IN", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Asia/Kolkata",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export function shortId(value: string): string {
  return value.length > 26 ? `${value.slice(0, 24)}…` : value;
}

export function compact(value: unknown, limit = 120): string {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  if (!text) return "—";
  return text.length > limit ? `${text.slice(0, limit)}…` : text;
}
