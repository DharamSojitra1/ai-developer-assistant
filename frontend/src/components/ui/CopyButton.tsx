import { Check, Copy } from "lucide-react";

import { useCopyToClipboard } from "@/hooks/useCopyToClipboard";
import { cn } from "@/lib/cn";

export function CopyButton({
  text,
  label = "Copy",
  showLabel = false,
  className,
}: {
  text: string;
  label?: string;
  showLabel?: boolean;
  className?: string;
}) {
  const { copied, copy } = useCopyToClipboard();
  const current = copied ? "Copied" : label;

  return (
    <button
      type="button"
      onClick={() => void copy(text)}
      aria-label={current}
      title={current}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md text-xs text-muted transition-colors hover:text-fg",
        showLabel ? "h-7 px-2 hover:bg-hover" : "size-7 justify-center hover:bg-hover",
        className,
      )}
    >
      {copied ? <Check className="size-3.5 text-success" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
      {showLabel && <span>{current}</span>}
      <span className="sr-only" aria-live="polite">
        {copied ? "Copied to clipboard" : ""}
      </span>
    </button>
  );
}
