/**
 * Format an ISO 8601 timestamp as a short relative time string.
 *
 * Examples:
 *   "just now", "5m ago", "3h ago", "2d ago", "08/04/2026"
 */
export function formatRelativeTime(iso: string): string {
  const parsed = new Date(iso);
  const ms = parsed.getTime();
  if (Number.isNaN(ms)) return "";

  const diffMs = Date.now() - ms;
  if (diffMs < 0) return "just now";

  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  return parsed.toLocaleDateString();
}
