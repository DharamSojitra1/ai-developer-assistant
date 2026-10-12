import { useEffect, useState } from "react";

import type { MascotMood } from "@/components/mascot/Mascot";

import type { AssistantStatus } from "./types";

export const HAPPY_MS = 1600;

const WORKING: ReadonlySet<AssistantStatus> = new Set(["pending", "streaming"]);
const FAILED: ReadonlySet<AssistantStatus> = new Set(["failed", "interrupted"]);

/** A reply that was being written just finished successfully. */
export function shouldCelebrate(previous: AssistantStatus, next: AssistantStatus, isLast: boolean): boolean {
  return isLast && WORKING.has(previous) && next === "completed";
}

export function assistantMood(status: AssistantStatus, celebrating: boolean, hasContent = false): MascotMood {
  if (status === "streaming" && hasContent) return "speaking";
  if (WORKING.has(status)) return "thinking";
  if (FAILED.has(status)) return "error";
  return celebrating ? "happy" : "idle";
}

export function useAssistantMood(status: AssistantStatus, isLast: boolean, hasContent = false): MascotMood {
  const [previous, setPrevious] = useState(status);
  const [celebrating, setCelebrating] = useState(false);

  if (previous !== status) {
    setPrevious(status);
    setCelebrating(shouldCelebrate(previous, status, isLast));
  }

  useEffect(() => {
    if (!celebrating) return;
    const timer = window.setTimeout(() => setCelebrating(false), HAPPY_MS);
    return () => window.clearTimeout(timer);
  }, [celebrating]);

  return assistantMood(status, celebrating, hasContent);
}
