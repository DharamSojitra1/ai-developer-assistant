import { useId, useRef, type KeyboardEvent, type ReactNode } from "react";

import { cn } from "@/lib/cn";

export interface TabItem<T extends string> {
  value: T;
  label: string;
  icon?: ReactNode;
}

/** Accessible tab list; render the active panel with `tabPanelProps`. */
export function Tabs<T extends string>({
  items,
  value,
  onChange,
  label,
  variant = "underline",
}: {
  items: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  variant?: "underline" | "pill";
}) {
  const baseId = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(event: KeyboardEvent, index: number) {
    let next: number | null = null;
    if (event.key === "ArrowRight") next = (index + 1) % items.length;
    if (event.key === "ArrowLeft") next = (index - 1 + items.length) % items.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = items.length - 1;
    if (next === null) return;
    event.preventDefault();
    onChange(items[next].value);
    refs.current[next]?.focus();
  }

  return (
    <div
      role="tablist"
      aria-label={label}
      className={cn(
        "flex gap-1 overflow-x-auto overflow-y-hidden",
        variant === "underline" ? "border-b border-border" : "inline-flex rounded-control border border-border bg-surface p-0.5",
      )}
    >
      {items.map((item, index) => {
        const selected = item.value === value;
        return (
          <button
            key={item.value}
            ref={(element) => {
              refs.current[index] = element;
            }}
            id={`${baseId}-${item.value}`}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.value)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={cn(
              "inline-flex shrink-0 items-center gap-2 text-sm font-medium transition-colors [&_svg]:size-4",
              variant === "underline"
                ? cn("-mb-px border-b-2 px-3 py-2.5", selected ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg")
                : cn("h-8 rounded-[0.375rem] px-3", selected ? "bg-elevated text-fg" : "text-muted hover:text-fg"),
            )}
          >
            {item.icon}
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
