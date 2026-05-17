export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const seconds = Math.round((Date.now() - then) / 1000);
  const abs = Math.abs(seconds);
  if (abs < 60) return "just now";
  if (abs < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (abs < 86_400) return `${Math.round(seconds / 3600)}h ago`;
  if (abs < 86_400 * 30) return `${Math.round(seconds / 86_400)}d ago`;
  if (abs < 86_400 * 365) return `${Math.round(seconds / (86_400 * 30))}mo ago`;
  return `${Math.round(seconds / (86_400 * 365))}y ago`;
}

export { formatClock, formatFullTimestamp } from "../parse-history";
