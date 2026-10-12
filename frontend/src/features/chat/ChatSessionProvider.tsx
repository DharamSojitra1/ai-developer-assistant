import { createContext, useCallback, useEffect, useMemo, useReducer, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { agentChat, decideApproval } from "@/api/agent";
import { getConversation, streamChat } from "@/api/chat";
import { ApiError, errorMessage, isAbortError } from "@/api/errors";
import { readTextStream } from "@/api/stream";
import { useLocalStorage } from "@/hooks/useLocalStorage";
import { createId } from "@/lib/format";

import { useHistory } from "../history/useHistory";

import { chatReducer, initialChatState, type ConversationLoad } from "./chatReducer";
import { createFrameBuffer } from "./frameBuffer";
import { conversationPath } from "./paths";
import type { ChatMessage, ChatMode } from "./types";

export interface ChatSessionValue {
  messages: ChatMessage[];
  conversationId: string | null;
  load: ConversationLoad;
  mode: ChatMode;
  setMode: (mode: ChatMode) => void;
  busy: boolean;
  send: (text: string) => boolean;
  stop: () => void;
  retry: (assistantId: string) => void;
  decide: (assistantId: string, approved: boolean) => void;
  newChat: () => void;
  /** Shows the conversation the URL names; null means a new chat. */
  showConversation: (conversationId: string | null) => void;
  reloadConversation: () => void;
  /** Leaves the open conversation (or only the given one) after it was deleted. */
  closeConversation: (conversationId?: string) => void;
}

// eslint-disable-next-line react-refresh/only-export-components
export const ChatSessionContext = createContext<ChatSessionValue | null>(null);

const isChatMode = (value: unknown): value is ChatMode => value === "agent" || value === "stream";

export function ChatSessionProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const [mode, setMode] = useLocalStorage<ChatMode>("ada.chat_mode", "agent", isChatMode);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const controllerRef = useRef<AbortController | null>(null);
  const messagesRef = useRef(state.messages);
  // Updated synchronously, so a send and the navigation it triggers agree on the conversation.
  const conversationIdRef = useRef<string | null>(null);
  const { refresh: refreshHistory } = useHistory();
  const navigate = useNavigate();

  useEffect(() => {
    messagesRef.current = state.messages;
  }, [state.messages]);

  const begin = useCallback(() => {
    const controller = new AbortController();
    controllerRef.current = controller;
    busyRef.current = true;
    setBusy(true);
    return controller;
  }, []);

  const end = useCallback((controller: AbortController) => {
    if (controllerRef.current !== controller) return;
    controllerRef.current = null;
    busyRef.current = false;
    setBusy(false);
  }, []);

  const run = useCallback(
    async (assistantId: string, prompt: string, runMode: ChatMode, conversationId: string) => {
      const controller = begin();
      const { signal } = controller;
      const request = { message: prompt, conversation_id: conversationId };

      try {
        if (runMode === "agent") {
          const response = await agentChat(request, signal);
          dispatch({ type: "agentResolved", id: assistantId, response });
          if (response.status === "completed") void refreshHistory();
          return;
        }

        const response = await streamChat(request, signal);
        const buffer = createFrameBuffer((text) => dispatch({ type: "append", id: assistantId, text }));
        const outcome = await readTextStream(response, buffer.push, signal);
        buffer.flush();
        dispatch({ type: "streamFinished", id: assistantId, outcome });
        if (outcome === "completed") void refreshHistory();
      } catch (error) {
        if (signal.aborted || isAbortError(error)) {
          dispatch({ type: "streamFinished", id: assistantId, outcome: "aborted" });
        } else {
          dispatch({ type: "failed", id: assistantId, error: errorMessage(error) });
        }
      } finally {
        end(controller);
      }
    },
    [begin, end, refreshHistory],
  );

  const send = useCallback(
    (text: string) => {
      const prompt = text.trim();
      if (!prompt || busyRef.current) return false;

      const isNew = conversationIdRef.current === null;
      const conversationId = conversationIdRef.current ?? createId();
      conversationIdRef.current = conversationId;

      const assistantId = createId();
      dispatch({ type: "submit", conversationId, userId: createId(), assistantId, prompt, mode, now: Date.now() });
      void run(assistantId, prompt, mode, conversationId);
      if (isNew) navigate(conversationPath(conversationId));
      return true;
    },
    [mode, run, navigate],
  );

  const stop = useCallback(() => controllerRef.current?.abort(), []);

  const retry = useCallback(
    (assistantId: string) => {
      const conversationId = conversationIdRef.current;
      if (busyRef.current || !conversationId) return;
      const message = messagesRef.current.find((item) => item.id === assistantId);
      if (!message || message.role !== "assistant" || message.mode === "history") return;

      dispatch({ type: "retry", id: assistantId, now: Date.now() });
      void run(assistantId, message.prompt, message.mode, conversationId);
    },
    [run],
  );

  const decide = useCallback(
    async (assistantId: string, approved: boolean) => {
      if (busyRef.current) return;
      const message = messagesRef.current.find((item) => item.id === assistantId);
      if (!message || message.role !== "assistant" || !message.runId) return;

      const controller = begin();
      dispatch({ type: "approvalSubmitting", id: assistantId, approved });

      try {
        const response = await decideApproval(message.runId, approved, controller.signal);
        dispatch({ type: "approvalResolved", id: assistantId, approved, response });
        if (response.status === "completed") void refreshHistory();
      } catch (error) {
        if (controller.signal.aborted) return;
        const closed = error instanceof ApiError && (error.status === 404 || error.status === 409);
        dispatch({
          type: "approvalFailed",
          id: assistantId,
          closed,
          error: closed ? "This request has expired or was already answered." : errorMessage(error),
        });
      } finally {
        end(controller);
      }
    },
    [begin, end, refreshHistory],
  );

  const abortCurrent = useCallback(() => {
    const controller = controllerRef.current;
    controller?.abort();
    if (controller) end(controller);
  }, [end]);

  const loadConversation = useCallback(
    async (conversationId: string) => {
      abortCurrent();
      conversationIdRef.current = conversationId;
      dispatch({ type: "loadStarted", conversationId });
      const controller = begin();

      try {
        const detail = await getConversation(conversationId, controller.signal);
        dispatch({ type: "loadSucceeded", conversationId, items: detail.messages, now: Date.now() });
      } catch (error) {
        if (controller.signal.aborted || isAbortError(error)) return;
        const notFound = error instanceof ApiError && (error.status === 404 || error.status === 422);
        dispatch({ type: "loadFailed", conversationId, notFound, error: errorMessage(error) });
      } finally {
        end(controller);
      }
    },
    [abortCurrent, begin, end],
  );

  const showConversation = useCallback(
    (conversationId: string | null) => {
      if (conversationId === conversationIdRef.current) return;

      if (conversationId === null) {
        abortCurrent();
        conversationIdRef.current = null;
        dispatch({ type: "reset" });
        return;
      }

      void loadConversation(conversationId);
    },
    [abortCurrent, loadConversation],
  );

  const reloadConversation = useCallback(() => {
    const conversationId = conversationIdRef.current;
    if (conversationId) void loadConversation(conversationId);
  }, [loadConversation]);

  const newChat = useCallback(() => navigate("/"), [navigate]);

  const closeConversation = useCallback(
    (conversationId?: string) => {
      if (conversationId !== undefined && conversationId !== conversationIdRef.current) return;
      abortCurrent();
      conversationIdRef.current = null;
      dispatch({ type: "reset" });
      if (window.location.pathname.startsWith("/c/")) navigate("/", { replace: true });
    },
    [abortCurrent, navigate],
  );

  useEffect(
    () => () => {
      controllerRef.current?.abort();
      // An aborted load must run again if this provider is remounted (StrictMode).
      conversationIdRef.current = null;
    },
    [],
  );

  const value = useMemo<ChatSessionValue>(
    () => ({
      messages: state.messages,
      conversationId: state.conversationId,
      load: state.load,
      mode,
      setMode,
      busy,
      send,
      stop,
      retry,
      decide: (id, approved) => void decide(id, approved),
      newChat,
      showConversation,
      reloadConversation,
      closeConversation,
    }),
    [
      state.messages,
      state.conversationId,
      state.load,
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
      closeConversation,
    ],
  );

  return <ChatSessionContext.Provider value={value}>{children}</ChatSessionContext.Provider>;
}
