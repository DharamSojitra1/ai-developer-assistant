import { ExternalLink, FileText, Globe } from "lucide-react";
import { useId, useState } from "react";

import type { SourceReference } from "@/api/types";

export interface SourceGroup {
  documentId: string;
  excerpts: string[];
  /** Only http(s) URLs, so a source can never become a javascript: link. */
  url?: string;
  title?: string;
}

function safeUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    const { protocol } = new URL(url);
    return protocol === "https:" || protocol === "http:" ? url : undefined;
  } catch {
    return undefined;
  }
}

// eslint-disable-next-line react-refresh/only-export-components
export function groupSources(sources: SourceReference[]): SourceGroup[] {
  const groups = new Map<string, SourceGroup>();

  for (const source of sources) {
    let group = groups.get(source.document_id);
    if (!group) {
      group = { documentId: source.document_id, excerpts: [] };
      const url = safeUrl(source.url);
      if (url) group.url = url;
      if (source.title) group.title = source.title;
      groups.set(source.document_id, group);
    }
    if (!group.excerpts.includes(source.text)) group.excerpts.push(source.text);
  }

  return Array.from(groups.values());
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

function SourceHeading({ group }: { group: SourceGroup }) {
  if (!group.url) {
    return (
      <>
        <FileText className="size-3.5 text-subtle" aria-hidden />
        <span className="truncate font-mono text-fg" title={group.documentId}>
          {group.documentId}
        </span>
      </>
    );
  }

  const hostname = new URL(group.url).hostname;

  return (
    <>
      <Globe className="size-3.5 shrink-0 text-subtle" aria-hidden />
      <a
        href={group.url}
        target="_blank"
        rel="noopener noreferrer"
        title={group.url}
        className="flex min-w-0 items-center gap-1 text-fg hover:text-accent hover:underline"
      >
        <span className="truncate">{group.title || hostname}</span>
        <ExternalLink className="size-3 shrink-0" aria-hidden />
        <span className="sr-only">(opens in a new tab)</span>
      </a>
      {group.title && <span className="shrink-0 truncate text-subtle">{hostname}</span>}
    </>
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
            <div className="mb-1.5 flex min-w-0 items-center gap-2 text-xs">
              <span className="flex size-5 shrink-0 items-center justify-center rounded bg-elevated font-mono text-[0.6875rem] text-muted">
                {index + 1}
              </span>
              <SourceHeading group={group} />
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
