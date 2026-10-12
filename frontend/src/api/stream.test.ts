import { describe, expect, it } from "vitest";

import { readTextStream } from "./stream";

/** Emits one chunk per read, then closes or fails, like a network stream. */
function streamOf(chunks: Uint8Array[], failAfter?: Error): ReadableStream<Uint8Array> {
  const queue = [...chunks];
  return new ReadableStream({
    pull(controller) {
      const next = queue.shift();
      if (next) controller.enqueue(next);
      else if (failAfter) controller.error(failAfter);
      else controller.close();
    },
  });
}

const encode = (text: string) => new TextEncoder().encode(text);

describe("readTextStream", () => {
  it("reports every chunk and completes", async () => {
    const received: string[] = [];
    const outcome = await readTextStream(new Response(streamOf([encode("Hel"), encode("lo")])), (text) => received.push(text));

    expect(outcome).toBe("completed");
    expect(received.join("")).toBe("Hello");
  });

  it("decodes multi-byte characters split across chunks", async () => {
    const bytes = encode("café ✓");
    let text = "";
    await readTextStream(new Response(streamOf([bytes.slice(0, 4), bytes.slice(4)])), (chunk) => (text += chunk));

    expect(text).toBe("café ✓");
  });

  it("keeps partial text and reports an interruption", async () => {
    let text = "";
    const outcome = await readTextStream(
      new Response(streamOf([encode("partial")], new TypeError("network error"))),
      (chunk) => (text += chunk),
    );

    expect(outcome).toBe("interrupted");
    expect(text).toBe("partial");
  });

  it("reports a user abort as aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    const outcome = await readTextStream(
      new Response(streamOf([], new DOMException("Aborted", "AbortError"))),
      () => undefined,
      controller.signal,
    );

    expect(outcome).toBe("aborted");
  });
});
