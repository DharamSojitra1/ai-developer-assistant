import { CheckCircle2, Equal } from "lucide-react";
import { useEffect, useRef } from "react";

import type { IndexDocumentResponse } from "@/api/types";
import { Badge } from "@/components/ui/Badge";

import { DOC_TYPE_LABELS } from "./constants";

export function IndexResult({ result }: { result: IndexDocumentResponse }) {
  const unchanged = result.status === "unchanged";
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ref.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [result]);

  return (
    <div ref={ref} role="status" className="mt-4 scroll-mb-6 rounded-panel border border-border bg-surface px-4 py-3 text-sm">
      <div className="flex items-center gap-2 font-medium">
        {unchanged ? (
          <Equal className="size-4 text-muted" aria-hidden />
        ) : (
          <CheckCircle2 className="size-4 text-success" aria-hidden />
        )}
        {unchanged ? "Already up to date" : "Indexed successfully"}
      </div>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[0.8125rem]">
        <dt className="text-subtle">Document ID</dt>
        <dd className="truncate font-mono text-xs leading-5">{result.document_id}</dd>
        <dt className="text-subtle">Source</dt>
        <dd className="truncate">{result.source}</dd>
        <dt className="text-subtle">Chunks</dt>
        <dd>
          {result.chunks_indexed} indexed
          <span className="text-subtle"> · {result.chunks_embedded} newly embedded</span>
        </dd>
      </dl>
      <div className="mt-2.5 flex gap-1.5">
        <Badge>{DOC_TYPE_LABELS[result.doc_type] ?? result.doc_type}</Badge>
        <Badge tone={result.visibility === "shared" ? "accent" : "neutral"}>{result.visibility}</Badge>
      </div>
    </div>
  );
}
