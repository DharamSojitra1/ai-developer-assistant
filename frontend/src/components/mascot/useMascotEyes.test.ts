import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { emitMascotSignal } from "./mascotSignals";
import {
  BLINK_MS,
  HELLO_DELAY_MS,
  KEY_PULSE_MS,
  KEY_THROTTLE_MS,
  REACT_MS,
  useMascotEyes,
  useMascotReactions,
  useMascotWave,
  WAVE_MS,
} from "./useMascotEyes";

function mockMatchMedia(matching: string[]) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: matching.includes(query),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

describe("useMascotEyes", () => {
  let element: HTMLSpanElement;

  beforeEach(() => {
    vi.useFakeTimers();
    element = document.createElement("span");
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("blinks at intervals and opens the eyes again", () => {
    mockMatchMedia([]);
    vi.spyOn(Math, "random").mockReturnValue(0.5);
    renderHook(() => useMascotEyes({ current: element }, { blink: true, track: false }));

    expect(element.hasAttribute("data-blink")).toBe(false);
    vi.advanceTimersByTime(4500);
    expect(element.hasAttribute("data-blink")).toBe(true);
    vi.advanceTimersByTime(BLINK_MS);
    expect(element.hasAttribute("data-blink")).toBe(false);
  });

  it("does not blink when reduced motion is preferred", () => {
    mockMatchMedia(["(prefers-reduced-motion: reduce)"]);
    renderHook(() => useMascotEyes({ current: element }, { blink: true, track: false }));
    vi.advanceTimersByTime(10_000);
    expect(element.hasAttribute("data-blink")).toBe(false);
  });

  it("tracks the pointer and cleans up on unmount", () => {
    mockMatchMedia(["(pointer: fine)"]);
    const add = vi.spyOn(window, "addEventListener");
    const remove = vi.spyOn(window, "removeEventListener");
    const { unmount } = renderHook(() => useMascotEyes({ current: element }, { blink: true, track: true }));

    const listener = add.mock.calls.find(([type]) => type === "pointermove")?.[1];
    expect(listener).toBeTypeOf("function");

    unmount();
    expect(remove).toHaveBeenCalledWith("pointermove", listener);
    vi.advanceTimersByTime(10_000);
    expect(element.hasAttribute("data-blink")).toBe(false);
    expect(element.style.getPropertyValue("--look-x")).toBe("");
  });
});

describe("useMascotWave", () => {
  let element: HTMLSpanElement;

  beforeEach(() => {
    vi.useFakeTimers();
    element = document.createElement("span");
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("waves on arrival, on click and after a long idle", () => {
    mockMatchMedia([]);
    vi.spyOn(Math, "random").mockReturnValue(0);
    renderHook(() => useMascotWave({ current: element }, true));

    vi.advanceTimersByTime(HELLO_DELAY_MS);
    expect(element.hasAttribute("data-wave")).toBe(true);
    vi.advanceTimersByTime(WAVE_MS);
    expect(element.hasAttribute("data-wave")).toBe(false);

    element.click();
    expect(element.hasAttribute("data-wave")).toBe(true);
    vi.advanceTimersByTime(WAVE_MS);

    window.dispatchEvent(new Event("keydown"));
    vi.advanceTimersByTime(10_000);
    expect(element.hasAttribute("data-wave")).toBe(false);
    vi.advanceTimersByTime(6_000);
    expect(element.hasAttribute("data-wave")).toBe(true);
  });

  it("stays still when disabled or when reduced motion is preferred", () => {
    mockMatchMedia(["(prefers-reduced-motion: reduce)"]);
    renderHook(() => useMascotWave({ current: element }, true));
    const other = document.createElement("span");
    renderHook(() => useMascotWave({ current: other }, false));

    vi.advanceTimersByTime(30_000);
    element.click();
    other.click();
    expect(element.hasAttribute("data-wave")).toBe(false);
    expect(other.hasAttribute("data-wave")).toBe(false);
  });
});

describe("useMascotReactions", () => {
  let element: HTMLSpanElement;

  beforeEach(() => {
    vi.useFakeTimers();
    element = document.createElement("span");
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("follows the caret, pulses on keys with throttling and shows word reactions", () => {
    mockMatchMedia([]);
    renderHook(() => useMascotReactions({ current: element }, true));

    emitMascotSignal({ type: "key", progress: 0.25 });
    expect(element.style.getPropertyValue("--read-x")).toBe("0.250");
    expect(element.hasAttribute("data-key")).toBe(true);
    vi.advanceTimersByTime(KEY_PULSE_MS);
    expect(element.hasAttribute("data-key")).toBe(false);

    emitMascotSignal({ type: "key", progress: 0.3 });
    expect(element.hasAttribute("data-key")).toBe(false);
    expect(element.style.getPropertyValue("--read-x")).toBe("0.300");
    vi.advanceTimersByTime(KEY_THROTTLE_MS);
    emitMascotSignal({ type: "key", progress: 0.35 });
    expect(element.hasAttribute("data-key")).toBe(true);

    emitMascotSignal({ type: "word", word: "question" });
    expect(element.dataset.react).toBe("question");
    emitMascotSignal({ type: "word", word: "thanks" });
    expect(element.dataset.react).toBe("thanks");
    vi.advanceTimersByTime(REACT_MS);
    expect(element.hasAttribute("data-react")).toBe(false);
  });

  it("ignores signals with reduced motion and cleans up on unmount", () => {
    mockMatchMedia(["(prefers-reduced-motion: reduce)"]);
    renderHook(() => useMascotReactions({ current: element }, true));
    emitMascotSignal({ type: "word", word: "thanks" });
    expect(element.hasAttribute("data-react")).toBe(false);

    mockMatchMedia([]);
    const other = document.createElement("span");
    const { unmount } = renderHook(() => useMascotReactions({ current: other }, true));
    emitMascotSignal({ type: "key", progress: 1 });
    emitMascotSignal({ type: "word", word: "question" });
    unmount();
    expect(other.hasAttribute("data-key")).toBe(false);
    expect(other.hasAttribute("data-react")).toBe(false);
    expect(other.style.getPropertyValue("--read-x")).toBe("");
    emitMascotSignal({ type: "word", word: "thanks" });
    expect(other.hasAttribute("data-react")).toBe(false);
  });
});
