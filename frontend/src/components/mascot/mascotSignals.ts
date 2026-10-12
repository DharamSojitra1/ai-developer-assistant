export type MascotSignal =
  | { type: "key"; progress: number }
  | { type: "word"; word: "question" | "thanks" };

const channel = new EventTarget();

/** Per-keystroke events for the mascot, kept out of React state so typing never re-renders it. */
export function emitMascotSignal(signal: MascotSignal) {
  channel.dispatchEvent(new CustomEvent<MascotSignal>("signal", { detail: signal }));
}

export function onMascotSignal(listener: (signal: MascotSignal) => void): () => void {
  const handler = (event: Event) => listener((event as CustomEvent<MascotSignal>).detail);
  channel.addEventListener("signal", handler);
  return () => channel.removeEventListener("signal", handler);
}
