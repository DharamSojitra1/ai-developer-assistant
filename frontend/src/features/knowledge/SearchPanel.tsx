import { Search, SearchX, Trash2 } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import { errorMessage, isAbortError } from "@/api/errors";
import { searchDocuments } from "@/api/rag";
import { MAX_SEARCH_QUERY_CHARS, type DocumentType, type SearchResult } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CopyButton } from "@/components/ui/CopyButton";
import { IconButton } from "@/components/ui/IconButton";
import { Select } from "@/components/ui/Select";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { fieldClass } from "@/components/ui/TextField";
import { cn } from "@/lib/cn";

import { DOC_TYPE_LABELS } from "./constants";

function Score({ label, value, title }: { label: string; value: number | null; title: string }) {
  if (value === null || value === undefined) return null;
  return (
    <span title={title} className="font-mono text-[0.6875rem] text-subtle">
      {label} {value.toFixed(3)}
    </span>
  );
}

function ResultItem({ result, rank, onDelete }: { result: SearchResult; rank: number; onDelete: (documentId: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const { metadata } = result;
  const documentId = typeof metadata.document_id === "string" ? metadata.document_id : null;
  const long = result.text.length > 360;

  return (
    <li className="rounded-panel border border-border bg-surface px-4 py-3.5">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="flex size-5 items-center justify-center rounded bg-elevated font-mono text-[0.6875rem] text-muted">{rank}</span>
        <span className="min-w-0 truncate text-sm font-medium">{metadata.source ?? documentId ?? result.id}</span>
        {metadata.doc_type && <Badge>{DOC_TYPE_LABELS[metadata.doc_type] ?? metadata.doc_type}</Badge>}
        {metadata.visibility && (
          <Badge tone={metadata.visibility === "shared" ? "accent" : "neutral"}>{metadata.visibility}</Badge>
        )}
        <div className="ml-auto flex items-center">
          {documentId && <CopyButton text={documentId} label="Copy document ID" />}
          {documentId && (
            <IconButton size="sm" label="Delete document" icon={<Trash2 />} onClick={() => onDelete(documentId)} />
          )}
        </div>
      </div>

      {(metadata.section || typeof metadata.chunk_index === "number") && (
        <p className="mt-1 truncate text-xs text-subtle">
          {metadata.section && <span>{metadata.section}</span>}
          {metadata.section && typeof metadata.chunk_index === "number" && " · "}
          {typeof metadata.chunk_index === "number" && <span>Chunk {metadata.chunk_index + 1}</span>}
        </p>
      )}

      <p className={cn("mt-2 whitespace-pre-wrap text-[0.8125rem] leading-6 text-muted", !expanded && long && "line-clamp-4")}>
        {result.text}
      </p>
      {long && (
        <button type="button" onClick={() => setExpanded((value) => !value)} className="mt-1 text-xs font-medium text-accent hover:underline">
          {expanded ? "Show less" : "Show more"}
        </button>
      )}

      <div className="mt-2.5 flex flex-wrap gap-x-3 gap-y-1">
        <Score label="rerank" value={result.rerank_score} title="Cross-encoder relevance score (higher is better)" />
        <Score label="distance" value={result.distance} title="Vector distance (lower is closer)" />
        <Score label="keyword" value={result.keyword_score} title="Keyword match score" />
        {documentId && <span className="truncate font-mono text-[0.6875rem] text-subtle">id {documentId}</span>}
      </div>
    </li>
  );
}

export function SearchPanel({ onDelete }: { onDelete: (documentId: string) => void }) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState("5");
  const [docType, setDocType] = useState<"" | DocumentType>("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  async function runSearch(event?: FormEvent) {
    event?.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;

    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    setLoading(true);
    setError(null);
    try {
      const response = await searchDocuments(
        { query: trimmed, top_k: Number(topK), doc_type: docType || undefined },
        controller.signal,
      );
      setResults(response.results);
    } catch (caught) {
      if (isAbortError(caught)) return;
      setError(errorMessage(caught));
    } finally {
      if (controllerRef.current === controller) setLoading(false);
    }
  }

  return (
    <div>
      <form onSubmit={runSearch} className="space-y-3" role="search">
        <div className="relative">
          <label htmlFor="kb-search" className="sr-only">
            Search your knowledge base
          </label>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle" aria-hidden />
          <input
            id="kb-search"
            type="search"
            value={query}
            maxLength={MAX_SEARCH_QUERY_CHARS}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by meaning or keywords…"
            className={cn(fieldClass, "h-11 pl-9 pr-28")}
          />
          <Button type="submit" size="sm" variant="primary" className="absolute right-1.5 top-1/2 -translate-y-1/2" loading={loading} disabled={!query.trim()}>
            Search
          </Button>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:max-w-sm">
          <Select
            label="Results"
            value={topK}
            onChange={(event) => setTopK(event.target.value)}
            options={["3", "5", "10", "20"].map((value) => ({ value, label: `Top ${value}` }))}
          />
          <Select
            label="Type"
            value={docType}
            onChange={(event) => setDocType(event.target.value as "" | DocumentType)}
            options={[
              { value: "", label: "Any type" },
              { value: "markdown", label: "Markdown" },
              { value: "text", label: "Text" },
              { value: "pdf", label: "PDF" },
            ]}
          />
        </div>
      </form>

      <div className="mt-6" aria-live="polite" aria-busy={loading}>
        {error && <ErrorState title="Search failed" message={error} onRetry={() => void runSearch()} />}
        {!error && loading && !results && (
          <div className="space-y-2">
            {[0, 1, 2].map((key) => (
              <div key={key} className="skeleton h-28 rounded-panel" />
            ))}
          </div>
        )}
        {!error && results && results.length === 0 && (
          <EmptyState
            icon={<SearchX />}
            title="No matching passages"
            description="Try different wording, or add documents that cover this topic."
          />
        )}
        {!error && results && results.length > 0 && (
          <ol className={cn("space-y-2.5 transition-opacity", loading && "opacity-60")}>
            {results.map((result, index) => (
              <ResultItem key={result.id} result={result} rank={index + 1} onDelete={onDelete} />
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
