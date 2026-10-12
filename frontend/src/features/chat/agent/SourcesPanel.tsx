import { FileText } from "lucide-react";
import { useId, useState } from "react";

import type { SourceReference } from "@/api/types";

export interface SourceGroup {
  documentId: string;
  excerpts: string[];
}

// eslint-disable-next-line react-refresh/only-export-components
export function groupSources(sources: SourceReference[]): SourceGroup[] {
  const groups = new Map<string, string[]>();

  for (const source of sources) {
    const excerpts = groups.get(source.document_id) ?? [];
    if (!excerpts.includes(source.text)) excerpts.push(source.text);
    groups.set(source.document_id, excerpts);
  }

  return Array.from(groups, ([documentId, excerpts]) => ({ documentId, excerpts }));
}

function Excerpt({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const long = text.length > 280;

  return (
    <div className="text-[0.8125rem] leading-6 text-muted">
      <p className={expanded || !long ? "whitespace-pre-wrap" : "line-clamp-3 whitespace-pre-wrap"}>{text}</p>
      {long && (
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="mt-1 text-xs font-medium text-accent hover:underline"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

export function SourcesPanel({ id, groups }: { id: string; groups: SourceGroup[] }) {
  const headingId = useId();

  return (
    <section id={id} aria-labelledby={headingId} className="mt-3 rounded-panel border border-border bg-surface">
      <h4 id={headingId} className="sr-only">
        Sources
      </h4>
      <ol className="divide-y divide-border">
        {groups.map((group, index) => (
          <li key={group.documentId} className="px-4 py-3">
            <div className="mb-1.5 flex items-center gap-2 text-xs">
              <span className="flex size-5 items-center justify-center rounded bg-elevated font-mono text-[0.6875rem] text-muted">
                {index + 1}
              </span>
              <FileText className="size-3.5 text-subtle" aria-hidden />
              <span className="truncate font-mono text-fg" title={group.documentId}>
                {group.documentId}
              </span>
              {group.excerpts.length > 1 && <span className="text-subtle">{group.excerpts.length} passages</span>}
            </div>
            <div className="space-y-2.5 pl-7">
              {group.excerpts.map((excerpt, excerptIndex) => (
                <Excerpt key={excerptIndex} text={excerpt} />
              ))}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
