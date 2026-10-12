import { ArrowUp, Square } from "lucide-react";
import { forwardRef, useImperativeHandle, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { CHAT_MAX_MESSAGE_CHARS } from "@/api/types";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/cn";

import type { ChatMode } from "./types";

const MAX_HEIGHT_PX = 200;
const COUNTER_THRESHOLD = Math.floor(CHAT_MAX_MESSAGE_CHARS * 0.8);

export interface ComposerHandle {
  focus: () => void;
}

export const Composer = forwardRef<
  ComposerHandle,
  {
    mode: ChatMode;
    busy: boolean;
    canStop: boolean;
    onSend: (text: string) => boolean;
    onStop: () => void;
    autoFocus?: boolean;
  }
>(function Composer({ mode, busy, canStop, onSend, onStop, autoFocus }, ref) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({ focus: () => textareaRef.current?.focus() }), []);

  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, MAX_HEIGHT_PX)}px`;
  }, [value]);

  const length = value.length;
  const tooLong = length > CHAT_MAX_MESSAGE_CHARS;
  const empty = !value.trim();
  const canSend = !busy && !empty && !tooLong;

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!canSend) return;
    if (onSend(value)) setValue("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    submit();
  }

  return (
    <form onSubmit={submit} className="w-full">
      <div
        className={cn(
          "rounded-[1.25rem] border bg-surface transition-colors focus-within:border-border-strong",
          tooLong ? "border-danger/60" : "border-border",
        )}
      >
        <label htmlFor="composer" className="sr-only">
          Message the assistant
        </label>
        <textarea
          id="composer"
          ref={textareaRef}
          value={value}
          rows={1}
          autoFocus={autoFocus}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder={mode === "agent" ? "Ask anything, or ask about your documents…" : "Ask anything…"}
          aria-describedby="composer-hint"
          aria-invalid={tooLong || undefined}
          className="block max-h-[200px] w-full resize-none bg-transparent px-4 pb-1 pt-3.5 text-[0.9375rem] leading-6 text-fg placeholder:text-subtle focus:outline-none"
        />
        <div className="flex items-center justify-between gap-3 px-2.5 pb-2.5 pl-4">
          <span
            className={cn("text-xs tabular-nums", tooLong ? "text-danger" : "text-subtle", length < COUNTER_THRESHOLD && "invisible")}
            aria-live={length >= COUNTER_THRESHOLD ? "polite" : undefined}
          >
            {length.toLocaleString()} / {CHAT_MAX_MESSAGE_CHARS.toLocaleString()}
          </span>
          {canStop ? (
            <button
              type="button"
              onClick={onStop}
              aria-label="Stop generating"
              title="Stop generating"
              className="flex size-8 items-center justify-center rounded-full bg-fg text-bg transition-opacity hover:opacity-85"
            >
              <Square className="size-3 fill-current" aria-hidden />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!canSend}
              aria-label={busy ? "Waiting for response" : "Send message"}
              title={busy ? "Waiting for response" : "Send message"}
              className="flex size-8 items-center justify-center rounded-full bg-accent text-accent-fg transition-colors hover:bg-accent-hover disabled:bg-elevated disabled:text-subtle"
            >
              {busy ? <Spinner className="size-4" /> : <ArrowUp className="size-4" strokeWidth={2.5} aria-hidden />}
            </button>
          )}
        </div>
      </div>
      <p id="composer-hint" className="mt-2 hidden text-center text-xs text-subtle sm:block">
        {mode === "agent"
          ? "Agent mode can search your knowledge base and use tools."
          : "Fast stream shows the answer as it's written, without tool details."}{" "}
        Enter to send, Shift+Enter for a new line.
      </p>
    </form>
  );
});
