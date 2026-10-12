import type { RefObject } from "react";

import { AssistantMessageItem, UserMessageItem } from "./MessageItem";
import type { ChatMessage } from "./types";

export function MessageList({
  messages,
  busy,
  containerRef,
  sentinelRef,
  onRetry,
  onDecide,
}: {
  messages: ChatMessage[];
  busy: boolean;
  containerRef: RefObject<HTMLDivElement>;
  sentinelRef: RefObject<HTMLDivElement>;
  onRetry: (id: string) => void;
  onDecide: (id: string, approved: boolean) => void;
}) {
  const lastId = messages[messages.length - 1]?.id;

  return (
    <div ref={containerRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div role="log" aria-label="Conversation" className="mx-auto w-full max-w-3xl space-y-8 px-4 pb-10 pt-4 sm:px-6">
        {messages.map((message) =>
          message.role === "user" ? (
            <UserMessageItem key={message.id} message={message} />
          ) : (
            <AssistantMessageItem
              key={message.id}
              message={message}
              isLast={message.id === lastId}
              busy={busy}
              onRetry={onRetry}
              onDecide={onDecide}
            />
          ),
        )}
      </div>
      <div ref={sentinelRef} aria-hidden className="h-px" />
    </div>
  );
}
