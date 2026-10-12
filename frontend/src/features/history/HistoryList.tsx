import { MessageSquareDashed, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { ConversationSummary } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { IconButton } from "@/components/ui/IconButton";
import { cn } from "@/lib/cn";
import { firstLine, formatDateTime, parseServerDate } from "@/lib/format";

import { conversationPath } from "../chat/paths";

import { DeleteConversationDialog } from "./DeleteConversationDialog";
import { groupByDate } from "./groupByDate";
import { useHistory } from "./useHistory";

export function HistoryList({ activeId, onNavigate }: { activeId: string | null; onNavigate: () => void }) {
  const { items, status, error, hasMore, loadingMore, refresh, loadMore } = useHistory();
  const groups = useMemo(() => groupByDate(items), [items]);
  const [pendingDelete, setPendingDelete] = useState<ConversationSummary | null>(null);

  if (status === "loading") {
    return (
      <div className="space-y-2 px-3 py-2" aria-busy="true" aria-label="Loading conversations">
        {[72, 88, 64, 80, 56, 76].map((width) => (
          <div key={width} className="skeleton h-4" style={{ width: `${width}%` }} />
        ))}
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="px-3 py-2 text-xs text-muted" role="alert">
        <p>{error ?? "Couldn't load conversations."}</p>
        <button type="button" onClick={() => void refresh()} className="mt-1.5 font-medium text-accent hover:underline">
          Try again
        </button>
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 text-xs text-subtle">
        <MessageSquareDashed className="size-3.5" aria-hidden />
        Your conversations will appear here.
      </div>
    );
  }

  return (
    <nav aria-label="Conversations" className="space-y-4 pb-2">
      {groups.map((group) => (
        <section key={group.label}>
          <h3 className="px-3 pb-1 text-[0.6875rem] font-medium uppercase tracking-wider text-subtle">{group.label}</h3>
          <ul className="space-y-px">
            {group.items.map((item) => {
              const active = item.id === activeId;
              const title = firstLine(item.title, 60) || "Untitled";
              return (
                <li key={item.id} className="group relative">
                  <Link
                    to={conversationPath(item.id)}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    title={`${firstLine(item.title, 200)}\n${formatDateTime(parseServerDate(item.updated_at))}`}
                    className={cn(
                      "block w-full truncate rounded-control py-1.5 pl-3 pr-9 text-[0.8125rem] transition-colors",
                      active ? "bg-hover text-fg" : "text-muted hover:bg-hover/70 hover:text-fg",
                    )}
                  >
                    {title}
                  </Link>
                  <IconButton
                    label={`Delete conversation: ${title}`}
                    title="Delete conversation"
                    icon={<Trash2 />}
                    size="sm"
                    onClick={() => setPendingDelete(item)}
                    className={cn(
                      "absolute right-1 top-1/2 -translate-y-1/2 focus-visible:opacity-100",
                      "group-hover:opacity-100 [@media(hover:none)]:opacity-100",
                      active ? "opacity-100" : "opacity-0",
                    )}
                  />
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      {error && <p className="px-3 text-xs text-danger" role="alert">{error}</p>}
      {hasMore && (
        <div className="px-1.5">
          <Button size="sm" variant="ghost" className="w-full" loading={loadingMore} onClick={() => void loadMore()}>
            Load more
          </Button>
        </div>
      )}
      <DeleteConversationDialog conversation={pendingDelete} onClose={() => setPendingDelete(null)} />
    </nav>
  );
}
