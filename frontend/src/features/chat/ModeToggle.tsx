import { Bot, Zap } from "lucide-react";
import { useRef, type KeyboardEvent, type ReactNode } from "react";

import { cn } from "@/lib/cn";

import type { ChatMode } from "./types";

const OPTIONS: { value: ChatMode; label: string; description: string; icon: ReactNode }[] = [
  {
    value: "agent",
    label: "Agent",
    description: "Uses tools and your knowledge base, and shows sources",
    icon: <Bot aria-hidden />,
  },
  {
    value: "stream",
    label: "Fast stream",
    description: "Streams the answer as it's written, without tool details",
    icon: <Zap aria-hidden />,
  },
];

export function ModeToggle({ mode, onChange, disabled }: { mode: ChatMode; onChange: (mode: ChatMode) => void; disabled?: boolean }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(event: KeyboardEvent, index: number) {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
    event.preventDefault();
    const next = (index + (event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : 1) + OPTIONS.length) % OPTIONS.length;
    onChange(OPTIONS[next].value);
    refs.current[next]?.focus();
  }

  return (
    <div
      role="radiogroup"
      aria-label="Response mode"
      className={cn("inline-flex shrink-0 rounded-control border border-border bg-surface p-0.5", disabled && "opacity-60")}
    >
      {OPTIONS.map((option, index) => {
        const checked = option.value === mode;
        return (
          <button
            key={option.value}
            ref={(element) => {
              refs.current[index] = element;
            }}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={checked ? 0 : -1}
            disabled={disabled}
            title={option.description}
            onClick={() => onChange(option.value)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={cn(
              "inline-flex h-7 items-center gap-1.5 whitespace-nowrap rounded-[0.375rem] px-2.5 text-[0.8125rem] font-medium transition-colors [&_svg]:size-3.5",
              checked ? "bg-elevated text-fg shadow-sm" : "text-muted hover:text-fg",
            )}
          >
            {option.icon}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
