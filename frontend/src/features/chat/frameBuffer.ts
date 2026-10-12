/** Coalesces streamed text into one state update per animation frame. */
export function createFrameBuffer(onFlush: (text: string) => void) {
  let pending = "";
  let frame: number | null = null;

  function flush() {
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    if (!pending) return;
    const text = pending;
    pending = "";
    onFlush(text);
  }

  function push(text: string) {
    pending += text;
    frame ??= requestAnimationFrame(() => {
      frame = null;
      flush();
    });
  }

  return { push, flush };
}
