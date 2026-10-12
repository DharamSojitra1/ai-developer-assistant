import { ChevronDown, RotateCw } from "lucide-react";
import { memo, useId, useMemo, useState } from "react";

import { LogoMark } from "@/components/layout/Logo";
import { Markdown } from "@/components/markdown/Markdown";
import { CopyButton } from "@/components/ui/CopyButton";
import { IconButton } from "@/components/ui/IconButton";
import { cn } from "@/lib/cn";

import { ApprovalCard } from "./agent/ApprovalCard";
import { RouteBadge } from "./agent/RouteBadge";
import { groupSources, SourcesPanel } from "./agent/SourcesPanel";
import { StatusIndicator, ThinkingIndicator } from "./agent/StatusIndicator";
import type { AssistantMessage, UserMessage } from "./types";
import { useAssistantMood } from "./useAssistantMood";

export const UserMessageItem = memo(function UserMessageItem({ message }: { message: UserMessage }) {
  return (
    <article aria-label="Your message" className="group flex flex-col items-end">
      <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-elevated px-4 py-2.5 text-[0.9375rem] leading-7 text-fg">
        {message.content}
      </div>
      <div className="mt-1 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100">
        <CopyButton text={message.content} label="Copy message" />
      </div>
    </article>
  );
});

const RETRYABLE = new Set(["failed", "interrupted", "stopped"]);

export const AssistantMessageItem = memo(function AssistantMessageItem({
  message,
  isLast,
  busy,
  onRetry,
  onDecide,
}: {
  message: AssistantMessage;
  isLast: boolean;
  busy: boolean;
  onRetry: (id: string) => void;
  onDecide: (id: string, approved: boolean) => void;
}) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const sourcesId = useId();
  const sourceGroups = useMemo(() => groupSources(message.sources ?? []), [message.sources]);

  const { status } = message;
  const working = status === "pending" || (status === "streaming" && !message.content);
  const showApproval = Boolean(message.approval?.length && message.approvalState);
  // Until a decision lands, `content` only holds the API's approval instructions, which the card replaces.
  const approvalUnresolved =
    status === "awaiting_approval" || (showApproval && message.approvalState?.phase !== "resolved");
  const showContent = Boolean(message.content) && !approvalUnresolved;
  const isAgent = message.mode === "agent";
  const settled = status !== "pending" && status !== "streaming";
  const showStatus = settled && !approvalUnresolved && status !== "completed";
  const mood = useAssistantMood(status, isLast, Boolean(message.content));

  return (
    <article aria-label="Assistant message" className="group flex gap-4">
      <div className="mt-0.5 hidden sm:block">
        <LogoMark mood={mood} still={!isLast} />
      </div>
      <div className="min-w-0 flex-1">
        {working && (
          <ThinkingIndicator
            startedAt={message.startedAt}
            label={isAgent ? "Working on it" : "Thinking"}
          />
        )}

        {showApproval && message.approval && message.approvalState && (
          <div className={showContent ? "mb-1" : undefined}>
            <ApprovalCard
              actions={message.approval}
              state={message.approvalState}
              disabled={busy}
              onDecide={(approved) => onDecide(message.id, approved)}
            />
          </div>
        )}

        {showContent && (
          <Markdown content={message.content} className={cn(status === "streaming" && "opacity-95")} />
        )}

        {message.error && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {message.error}
          </p>
        )}
        {status === "stopped" && !message.error && (
          <p className="mt-3 text-sm text-muted">You stopped this response.</p>
        )}

        {(settled || status === "streaming") && !working && (
          <div className="mt-3 flex min-h-7 flex-wrap items-center gap-2">
            {status === "streaming" && (
              <span className="flex items-center gap-1.5 text-xs text-subtle" role="status">
                <span className="size-1.5 rounded-full bg-accent" style={{ animation: "pulse-soft 1s ease-in-out infinite" }} />
                Generating
              </span>
            )}
            {showStatus && <StatusIndicator status={status} />}
            {message.route && <RouteBadge route={message.route} />}
            {sourceGroups.length > 0 && (
              <button
                type="button"
                aria-expanded={sourcesOpen}
                aria-controls={sourcesId}
                onClick={() => setSourcesOpen((open) => !open)}
                className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-xs font-medium text-muted transition-colors hover:border-border-strong hover:text-fg"
              >
                {sourceGroups.length === 1 ? "1 source" : `${sourceGroups.length} sources`}
                <ChevronDown className={cn("size-3 transition-transform", sourcesOpen && "rotate-180")} aria-hidden />
              </button>
            )}

            {settled && (
              <div
                className={cn(
                  "ml-auto flex items-center gap-0.5 transition-opacity",
                  !isLast && "sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100",
                )}
              >
                {RETRYABLE.has(status) && (
                  <IconButton size="sm" label="Retry" icon={<RotateCw />} disabled={busy} onClick={() => onRetry(message.id)} />
                )}
                {showContent && <CopyButton text={message.content} label="Copy response" />}
              </div>
            )}
          </div>
        )}

        {sourcesOpen && sourceGroups.length > 0 && <SourcesPanel id={sourcesId} groups={sourceGroups} />}
      </div>
    </article>
  );
});
