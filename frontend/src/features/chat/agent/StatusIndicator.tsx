import { AlertTriangle, CircleSlash, ShieldAlert, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/Badge";

import type { AssistantStatus } from "../types";

export function ThinkingIndicator({ startedAt, label = "Thinking" }: { startedAt: number; label?: string }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const seconds = Math.max(0, Math.floor((now - startedAt) / 1000));

  return (
    <div className="flex h-7 items-center gap-2.5 text-sm text-muted" role="status">
      <span className="flex gap-1" aria-hidden>
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="size-1.5 rounded-full bg-muted"
            style={{ animation: "pulse-soft 1.2s ease-in-out infinite", animationDelay: `${delay}ms` }}
          />
        ))}
      </span>
      <span>
        {label}
        {seconds >= 3 && <span className="ml-1.5 tabular-nums text-subtle">{seconds}s</span>}
      </span>
    </div>
  );
}

/** Shown for every state except plain success, which needs no badge. */
export function StatusIndicator({ status }: { status: AssistantStatus }) {
  switch (status) {
    case "awaiting_approval":
      return (
        <Badge tone="warning" icon={<ShieldAlert aria-hidden />}>
          Needs approval
        </Badge>
      );
    case "failed":
      return (
        <Badge tone="danger" icon={<XCircle aria-hidden />}>
          Failed
        </Badge>
      );
    case "interrupted":
      return (
        <Badge tone="warning" icon={<AlertTriangle aria-hidden />}>
          Interrupted
        </Badge>
      );
    case "stopped":
      return (
        <Badge icon={<CircleSlash aria-hidden />}>
          Stopped
        </Badge>
      );
    default:
      return null;
  }
}
