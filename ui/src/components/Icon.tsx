const PATHS: Record<string, string> = {
  overview: "M4 13h6V4H4v9Zm0 7h6v-5H4v5Zm10 0h6v-9h-6v9Zm0-16v5h6V4h-6Z",
  run: "M12 3a9 9 0 1 0 9 9h-9V3Z M12 3v9h9A9 9 0 0 0 12 3Z",
  attack: "M12 2 3 7v6c0 5 4 8 9 9 5-1 9-4 9-9V7l-9-5Zm0 6v5m0 3h.01",
  policy: "M6 3h9l4 4v14H6V3Zm8 0v5h5M9 13h6M9 17h6M9 9h2",
  report: "M7 3h7l4 4v14H7V3Zm6 0v5h5M10 12h5M10 16h5",
  arrow: "M5 12h14m-6-6 6 6-6 6",
  download: "M12 3v12m0 0 4-4m-4 4-4-4M5 19h14",
  copy: "M9 9h10v10H9V9Zm-4 6H3V3h12v2",
  external: "M14 4h6v6m0-6-8 8M20 14v6H4V4h6",
  check: "M5 12l4 4L19 6",
  close: "M6 6l12 12M18 6 6 18",
};

export function Icon({ name, size = 18 }: { name: keyof typeof PATHS | string; size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" className="icon">
      <path d={PATHS[name] ?? PATHS.overview} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
