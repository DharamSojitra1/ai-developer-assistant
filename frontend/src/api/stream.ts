import { isAbortError } from "./errors";

/**
 * - `completed`: the server closed the stream normally.
 * - `aborted`: the user stopped it.
 * - `interrupted`: the connection dropped or the server failed mid-stream.
 */
export type StreamOutcome = "completed" | "aborted" | "interrupted";

/** Reads a `text/plain` streaming response, reporting each decoded chunk. */
export async function readTextStream(
  response: Response,
  onText: (text: string) => void,
  signal?: AbortSignal,
): Promise<StreamOutcome> {
  if (!response.body) {
    const text = await response.text();
    if (text) onText(text);
    return "completed";
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;

      const text = decoder.decode(value, { stream: true });
      if (text) onText(text);
    }

    const tail = decoder.decode();
    if (tail) onText(tail);
    return "completed";
  } catch (error) {
    if (signal?.aborted || isAbortError(error)) return "aborted";
    return "interrupted";
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // Already released by a cancelled read.
    }
  }
}
