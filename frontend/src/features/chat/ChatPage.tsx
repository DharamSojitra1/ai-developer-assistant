import { ArrowDown, MessageSquareOff, SquarePen } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { TopBar } from "@/components/layout/TopBar";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState } from "@/components/ui/States";

import { Composer, type ComposerHandle, type DraftState } from "./Composer";
import { MessageList } from "./MessageList";
import { ModeToggle } from "./ModeToggle";
import { useAutoScroll } from "./useAutoScroll";
import { useChatSession } from "./useChatSession";
import { StarterPrompts, WelcomeHeading } from "./WelcomeScreen";

function ConversationSkeleton() {
  return (
    <div className="mx-auto w-full max-w-3xl space-y-8 px-4 py-8 sm:px-6" aria-busy="true" aria-label="Loading conversation">
      {[0, 1].map((turn) => (
        <div key={turn} className="space-y-3">
          <div className="skeleton ml-auto h-9 w-2/5 rounded-2xl" />
          <div className="space-y-2">
            <div className="skeleton h-4 w-11/12" />
            <div className="skeleton h-4 w-4/5" />
            <div className="skeleton h-4 w-3/5" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function ChatPage() {
  const {
    messages,
    conversationId,
    load,
    mode,
    setMode,
    busy,
    send,
    stop,
    retry,
    decide,
    newChat,
    showConversation,
    reloadConversation,
  } = useChatSession();
  const { conversationId: routeConversationId } = useParams();
  const composerRef = useRef<ComposerHandle>(null);
  const [draft, setDraft] = useState<DraftState>("empty");
  const last = messages[messages.length - 1];
  const contentKey = last ? `${messages.length}:${last.role === "assistant" ? `${last.content.length}:${last.status}` : ""}` : "";
  const streaming = last?.role === "assistant" && last.status === "streaming";
  const loading = load.status === "loading";
  const empty = messages.length === 0 && load.status === "idle";
  const lastUserId = [...messages].reverse().find((message) => message.role === "user")?.id;
  const { containerRef, sentinelRef, atBottom, scrollToBottom } = useAutoScroll(contentKey, messages.length > 0, {
    turnKey: lastUserId,
    anchorToLastMessage: last?.role === "assistant" && last.mode !== "stream",
  });

  // The URL decides which conversation is on screen.
  useEffect(() => {
    showConversation(routeConversationId ?? null);
  }, [routeConversationId, showConversation]);

  useEffect(() => {
    if (empty || (load.status === "idle" && conversationId)) composerRef.current?.focus();
  }, [empty, load.status, conversationId]);

  const composer = (
    <Composer
      ref={composerRef}
      mode={mode}
      busy={busy}
      canStop={busy && streaming}
      onSend={send}
      onStop={stop}
      onDraftChange={setDraft}
      autoFocus
    />
  );

  const newChatButton = (
    <Button variant="secondary" icon={<SquarePen className="size-4" />} onClick={newChat}>
      New chat
    </Button>
  );

  let body;
  if (load.status === "not_found") {
    body = (
      <div className="flex flex-1 items-center justify-center">
        <EmptyState
          icon={<MessageSquareOff />}
          title="Conversation not found"
          description="It may have been deleted, or it belongs to a different account."
          action={newChatButton}
        />
      </div>
    );
  } else if (load.status === "error") {
    body = (
      <div className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6">
        <ErrorState title="Couldn't load this conversation" message={load.error} onRetry={reloadConversation} />
      </div>
    );
  } else if (loading) {
    body = <ConversationSkeleton />;
  } else if (empty) {
    body = (
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4">
        <div className="mx-auto my-auto w-full max-w-3xl py-10 short:py-5">
          <WelcomeHeading
            mood={busy ? "thinking" : draft === "typing" ? "typing" : draft === "paused" ? "waiting" : "idle"}
          />
          {composer}
          <StarterPrompts onPick={send} disabled={busy} />
        </div>
      </div>
    );
  } else {
    body = (
      <>
        <div className="relative flex min-h-0 flex-1 flex-col">
          <MessageList
            messages={messages}
            busy={busy}
            containerRef={containerRef}
            sentinelRef={sentinelRef}
            onRetry={retry}
            onDecide={decide}
          />
          {!atBottom && (
            <button
              type="button"
              onClick={() => scrollToBottom()}
              className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-border bg-elevated px-3 py-1.5 text-xs font-medium text-fg shadow-lg transition-colors hover:bg-hover"
            >
              <ArrowDown className="size-3.5" aria-hidden />
              Jump to latest
            </button>
          )}
        </div>
        <div className="shrink-0 px-3 pb-3 pt-1 sm:px-6 sm:pb-4">
          <div className="mx-auto w-full max-w-3xl">{composer}</div>
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar>
        <ModeToggle mode={mode} onChange={setMode} disabled={busy} />
      </TopBar>

      <p className="sr-only" aria-live="polite">
        {loading
          ? "Loading conversation."
          : busy
            ? "The assistant is responding."
            : last?.role === "assistant"
              ? "Response ready."
              : ""}
      </p>

      {body}
    </>
  );
}
