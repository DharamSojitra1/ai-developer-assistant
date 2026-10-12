import type { ConversationSummary } from "@/api/types";
import { parseServerDate } from "@/lib/format";

export interface HistoryGroup {
  label: string;
  items: ConversationSummary[];
}

const DAY_MS = 24 * 60 * 60 * 1000;

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

function labelFor(date: Date, now: Date): string {
  const days = Math.round((startOfDay(now) - startOfDay(date)) / DAY_MS);

  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return "Previous 7 days";
  if (days < 30) return "Previous 30 days";
  return "Older";
}

/** Groups most-recently-active-first conversations into date buckets, preserving order. */
export function groupByDate(items: ConversationSummary[], now = new Date()): HistoryGroup[] {
  const groups: HistoryGroup[] = [];

  for (const item of items) {
    const label = labelFor(parseServerDate(item.updated_at), now);
    const last = groups[groups.length - 1];

    if (last?.label === label) last.items.push(item);
    else groups.push({ label, items: [item] });
  }

  return groups;
}
