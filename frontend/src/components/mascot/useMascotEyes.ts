import { useEffect, type RefObject } from "react";

export const BLINK_MS = 140;
const BLINK_MIN_GAP_MS = 2500;
const BLINK_MAX_GAP_MS = 6500;
const DOUBLE_BLINK_CHANCE = 0.15;
const LOOK_RANGE = 2.5;
const TILT_RANGE_DEG = 8;
const TRACK_IDLE_MS = 2500;
export const WAVE_MS = 1400;
export const HELLO_DELAY_MS = 700;
const IDLE_WAVE_MIN_MS = 15_000;
const IDLE_WAVE_MAX_MS = 20_000;

function matches(query: string): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia(query).matches;
}

function clamp(value: number): number {
  return Math.max(-1, Math.min(1, value));
}

/**
 * Drives blinking and cursor tracking by writing data attributes and CSS variables on `ref`,
 * so the mascot never re-renders for them.
 */
export function useMascotEyes(
  ref: RefObject<HTMLElement | null>,
  { blink, track }: { blink: boolean; track: boolean },
) {
  useEffect(() => {
    const element = ref.current;
    if (!element || !blink || matches("(prefers-reduced-motion: reduce)")) return;

    let timer: number | undefined;

    const schedule = () => {
      const gap = BLINK_MIN_GAP_MS + Math.random() * (BLINK_MAX_GAP_MS - BLINK_MIN_GAP_MS);
      timer = window.setTimeout(() => close(Math.random() < DOUBLE_BLINK_CHANCE ? 2 : 1), gap);
    };

    const close = (times: number) => {
      element.dataset.blink = "";
      timer = window.setTimeout(() => {
        delete element.dataset.blink;
        if (times > 1) timer = window.setTimeout(() => close(times - 1), BLINK_MS);
        else schedule();
      }, BLINK_MS);
    };

    schedule();
    return () => {
      window.clearTimeout(timer);
      delete element.dataset.blink;
    };
  }, [ref, blink]);

  useEffect(() => {
    const element = ref.current;
    if (!element || !track || !matches("(pointer: fine)") || matches("(prefers-reduced-motion: reduce)")) return;

    let frame = 0;
    let idleTimer: number | undefined;
    let pointer: { x: number; y: number } | null = null;

    const reset = () => {
      for (const name of ["--look-x", "--look-y", "--tilt-x", "--tilt-y"]) element.style.removeProperty(name);
      delete element.dataset.tracking;
    };

    const apply = () => {
      frame = 0;
      if (!pointer) return;
      const rect = element.getBoundingClientRect();
      const reach = Math.max(rect.width * 3, 320);
      const x = clamp((pointer.x - (rect.left + rect.width / 2)) / reach);
      const y = clamp((pointer.y - (rect.top + rect.height / 2)) / reach);
      element.style.setProperty("--look-x", `${(x * LOOK_RANGE).toFixed(2)}px`);
      element.style.setProperty("--look-y", `${(y * LOOK_RANGE).toFixed(2)}px`);
      element.style.setProperty("--tilt-x", `${(x * TILT_RANGE_DEG).toFixed(2)}deg`);
      element.style.setProperty("--tilt-y", `${(-y * TILT_RANGE_DEG).toFixed(2)}deg`);
      element.dataset.tracking = "";
    };

    const onPointerMove = (event: PointerEvent) => {
      pointer = { x: event.clientX, y: event.clientY };
      if (!frame) frame = window.requestAnimationFrame(apply);
      window.clearTimeout(idleTimer);
      idleTimer = window.setTimeout(reset, TRACK_IDLE_MS);
    };

    window.addEventListener("pointermove", onPointerMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.cancelAnimationFrame(frame);
      window.clearTimeout(idleTimer);
      reset();
    };
  }, [ref, track]);
}

/**
 * Sets `data-wave` on `ref` for a one-handed wave: once on arrival, when clicked, and after
 * 15–20 s without keyboard or pointer activity.
 */
export function useMascotWave(ref: RefObject<HTMLElement | null>, enabled: boolean) {
  useEffect(() => {
    const element = ref.current;
    if (!element || !enabled || matches("(prefers-reduced-motion: reduce)")) return;

    const nextGap = () => IDLE_WAVE_MIN_MS + Math.random() * (IDLE_WAVE_MAX_MS - IDLE_WAVE_MIN_MS);
    let lastActive = Date.now();
    let gap = nextGap();
    let waveTimer: number | undefined;

    const wave = () => {
      lastActive = Date.now();
      if (element.dataset.wave !== undefined) return;
      element.dataset.wave = "";
      waveTimer = window.setTimeout(() => delete element.dataset.wave, WAVE_MS);
    };

    const onActivity = () => {
      lastActive = Date.now();
    };

    const helloTimer = window.setTimeout(wave, HELLO_DELAY_MS);
    const idleCheck = window.setInterval(() => {
      if (document.hidden || Date.now() - lastActive < gap) return;
      wave();
      gap = nextGap();
    }, 1000);

    const activityEvents = ["keydown", "pointerdown", "pointermove"] as const;
    for (const type of activityEvents) window.addEventListener(type, onActivity, { passive: true });
    element.addEventListener("click", wave);

    return () => {
      window.clearTimeout(helloTimer);
      window.clearTimeout(waveTimer);
      window.clearInterval(idleCheck);
      for (const type of activityEvents) window.removeEventListener(type, onActivity);
      element.removeEventListener("click", wave);
      delete element.dataset.wave;
    };
  }, [ref, enabled]);
}
