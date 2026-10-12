import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AssistantStatus } from "./types";
import { assistantMood, HAPPY_MS, shouldCelebrate, useAssistantMood } from "./useAssistantMood";

describe("assistantMood", () => {
  it("thinks while the reply is pending or streaming", () => {
    expect(assistantMood("pending", false)).toBe("thinking");
    expect(assistantMood("streaming", true)).toBe("thinking");
  });

  it("speaks once streamed text arrives", () => {
    expect(assistantMood("streaming", false, true)).toBe("speaking");
    expect(assistantMood("streaming", false, false)).toBe("thinking");
    expect(assistantMood("pending", false, true)).toBe("thinking");
  });

  it("looks worried when a reply fails or is interrupted, but not when stopped", () => {
    expect(assistantMood("failed", false)).toBe("error");
    expect(assistantMood("interrupted", false, true)).toBe("error");
    expect(assistantMood("stopped", false, true)).toBe("idle");
  });

  it("is happy only while celebrating a settled reply", () => {
    expect(assistantMood("completed", true)).toBe("happy");
    expect(assistantMood("completed", false)).toBe("idle");
  });
});

describe("shouldCelebrate", () => {
  it("celebrates when the last reply finishes", () => {
    expect(shouldCelebrate("streaming", "completed", true)).toBe(true);
    expect(shouldCelebrate("pending", "completed", true)).toBe(true);
  });

  it("does not celebrate failures, older messages or replies that were never in progress", () => {
    expect(shouldCelebrate("streaming", "failed", true)).toBe(false);
    expect(shouldCelebrate("streaming", "stopped", true)).toBe(false);
    expect(shouldCelebrate("streaming", "completed", false)).toBe(false);
    expect(shouldCelebrate("awaiting_approval", "completed", true)).toBe(false);
  });
});

describe("useAssistantMood", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("goes thinking, then happy, then back to idle", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(({ status }) => useAssistantMood(status, true), {
      initialProps: { status: "streaming" as AssistantStatus },
    });
    expect(result.current).toBe("thinking");

    rerender({ status: "completed" });
    expect(result.current).toBe("happy");

    act(() => {
      vi.advanceTimersByTime(HAPPY_MS);
    });
    expect(result.current).toBe("idle");
  });

  it("stays idle for a reply loaded from history", () => {
    const { result } = renderHook(() => useAssistantMood("completed", true));
    expect(result.current).toBe("idle");
  });
});
