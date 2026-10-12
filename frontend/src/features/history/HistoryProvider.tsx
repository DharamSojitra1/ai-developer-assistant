import { createContext, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { deleteChatHistory, deleteConversation, listConversations } from "@/api/chat";
import { ApiError, errorMessage } from "@/api/errors";
import type { ConversationSummary } from "@/api/types";

export const HISTORY_PAGE_SIZE = 20;

export interface HistoryContextValue {
  items: ConversationSummary[];
  status: "loading" | "ready" | "error";
  error: string | null;
  hasMore: boolean;
  loadingMore: boolean;
  refresh: () => Promise<void>;
  loadMore: () => Promise<void>;
  /** Deletes one conversation; resolves once it is gone from the server. */
  remove: (conversationId: string) => Promise<void>;
  clearAll: () => Promise<number>;
}

// eslint-disable-next-line react-refresh/only-export-components
export const HistoryContext = createContext<HistoryContextValue | null>(null);

export function HistoryProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [status, setStatus] = useState<HistoryContextValue["status"]>("loading");
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const requestId = useRef(0);

  const refresh = useCallback(async () => {
    const id = ++requestId.current;
    setError(null);

    try {
      const page = await listConversations({ limit: HISTORY_PAGE_SIZE, skip: 0 });
      if (id !== requestId.current) return;
      setItems(page.conversations);
      setHasMore(page.count === HISTORY_PAGE_SIZE);
      setStatus("ready");
    } catch (caught) {
      if (id !== requestId.current) return;
      setError(errorMessage(caught));
      setStatus((current) => (current === "ready" ? current : "error"));
    }
  }, []);

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    const id = requestId.current;
    setLoadingMore(true);

    try {
      const page = await listConversations({ limit: HISTORY_PAGE_SIZE, skip: items.length });
      if (id !== requestId.current) return;
      setItems((current) => {
        const known = new Set(current.map((item) => item.id));
        return [...current, ...page.conversations.filter((item) => !known.has(item.id))];
      });
      setHasMore(page.count === HISTORY_PAGE_SIZE);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoadingMore(false);
    }
  }, [hasMore, items.length, loadingMore]);

  const remove = useCallback(async (conversationId: string) => {
    try {
      await deleteConversation(conversationId);
    } catch (caught) {
      // Already gone, e.g. deleted in another tab.
      if (!(caught instanceof ApiError && caught.status === 404)) throw caught;
    }
    requestId.current++;
    setItems((current) => current.filter((item) => item.id !== conversationId));
  }, []);

  const clearAll = useCallback(async () => {
    const result = await deleteChatHistory();
    requestId.current++;
    setItems([]);
    setHasMore(false);
    setStatus("ready");
    return result.deleted;
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({ items, status, error, hasMore, loadingMore, refresh, loadMore, remove, clearAll }),
    [items, status, error, hasMore, loadingMore, refresh, loadMore, remove, clearAll],
  );

  return <HistoryContext.Provider value={value}>{children}</HistoryContext.Provider>;
}
