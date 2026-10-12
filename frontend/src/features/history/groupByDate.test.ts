import { describe, expect, it } from "vitest";

import type { ConversationSummary } from "@/api/types";
import { parseServerDate } from "@/lib/format";

import { groupByDate } from "./groupByDate";

function item(id: string, updatedAt: Date): ConversationSummary {
  const timestamp = updatedAt.toISOString().replace("Z", "");
  return { id, title: id, message_count: 1, created_at: "2026-01-01T00:00:00", updated_at: timestamp };
}

describe("parseServerDate", () => {
  it("treats naive timestamps from the API as UTC", () => {
    expect(parseServerDate("2026-10-11T08:00:00").toISOString()).toBe("2026-10-11T08:00:00.000Z");
    expect(parseServerDate("2026-10-11T08:00:00+00:00").toISOString()).toBe("2026-10-11T08:00:00.000Z");
  });
});

describe("groupByDate", () => {
  it("buckets conversations by the day they were last active", () => {
    const now = new Date(2026, 9, 11, 15, 0);
    const daysAgo = (days: number) => new Date(2026, 9, 11 - days, 12, 0);

    const groups = groupByDate(
      [item("a", daysAgo(0)), item("b", daysAgo(1)), item("c", daysAgo(3)), item("d", daysAgo(12)), item("e", daysAgo(60))],
      now,
    );

    expect(groups.map((group) => [group.label, group.items.map((entry) => entry.id)])).toEqual([
      ["Today", ["a"]],
      ["Yesterday", ["b"]],
      ["Previous 7 days", ["c"]],
      ["Previous 30 days", ["d"]],
      ["Older", ["e"]],
    ]);
  });

  it("returns no groups for empty history", () => {
    expect(groupByDate([])).toEqual([]);
  });
});
