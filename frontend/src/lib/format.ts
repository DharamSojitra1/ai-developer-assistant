const TIMEZONE_SUFFIX = /(Z|[+-]\d{2}:?\d{2})$/i;

/**
 * The backend stores UTC datetimes but serializes them without an offset
 * (MongoDB returns naive datetimes), so a bare timestamp is treated as UTC.
 */
export function parseServerDate(value: string): Date {
  return new Date(TIMEZONE_SUFFIX.test(value) ? value : `${value}Z`);
}

const numberFormat = new Intl.NumberFormat();
const compactFormat = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 });

export function formatNumber(value: number): string {
  return numberFormat.format(value);
}

export function formatCompact(value: number): string {
  return compactFormat.format(value);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDateTime(date: Date): string {
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function firstLine(text: string, max = 80): string {
  const line = text.trim().split(/\r?\n/, 1)[0] ?? "";
  return line.length > max ? `${line.slice(0, max - 1).trimEnd()}…` : line;
}

export function createId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
