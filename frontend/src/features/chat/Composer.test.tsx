import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { onMascotSignal, type MascotSignal } from "@/components/mascot/mascotSignals";

import { Composer } from "./Composer";

function setup() {
  const onDraftChange = vi.fn();
  render(<Composer mode="agent" busy={false} canStop={false} onSend={() => true} onStop={() => {}} onDraftChange={onDraftChange} />);
  const textarea = screen.getByRole("textbox", { name: "Message the assistant" });
  const type = (value: string) => fireEvent.change(textarea, { target: { value } });
  return { onDraftChange, type };
}

describe("Composer stop button", () => {
  it("replaces Send with Stop while a reply can be stopped", () => {
    const onStop = vi.fn();
    render(<Composer mode="agent" busy canStop onSend={() => true} onStop={onStop} />);

    fireEvent.click(screen.getByRole("button", { name: "Stop generating" }));

    expect(onStop).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Waiting for response" })).toBeNull();
  });
});

describe("Composer typing signals", () => {
  let signals: MascotSignal[];
  let unsubscribe: () => void;

  beforeEach(() => {
    vi.useFakeTimers();
    signals = [];
    unsubscribe = onMascotSignal((signal) => signals.push(signal));
  });

  afterEach(() => {
    unsubscribe();
    vi.useRealTimers();
  });

  it("reports typing, then paused after a short pause, then empty when cleared", () => {
    const { onDraftChange, type } = setup();

    type("hello");
    expect(onDraftChange).toHaveBeenLastCalledWith("typing");

    act(() => vi.advanceTimersByTime(1200));
    expect(onDraftChange).toHaveBeenLastCalledWith("paused");

    type("");
    expect(onDraftChange).toHaveBeenLastCalledWith("empty");
  });

  it("emits key signals with the caret's progress along the line", () => {
    const { type } = setup();

    type("a".repeat(30));
    expect(signals.at(-1)).toEqual({ type: "key", progress: 0.5 });

    type(`${"a".repeat(30)}\nab`);
    expect(signals.at(-1)?.type).toBe("key");
    expect((signals.at(-1) as { progress: number }).progress).toBeCloseTo(2 / 60);
  });

  it("emits one word signal per question mark or thanks", () => {
    const { type } = setup();
    const words = () => signals.filter((signal) => signal.type === "word");

    type("why");
    type("why?");
    type("why??");
    expect(words()).toEqual([{ type: "word", word: "question" }]);

    type("ok thank");
    type("ok thanks");
    type("ok thanks!");
    expect(words()).toEqual([
      { type: "word", word: "question" },
      { type: "word", word: "thanks" },
    ]);
  });
});
