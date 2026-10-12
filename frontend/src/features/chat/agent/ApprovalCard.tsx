import { AlertTriangle, CheckCircle2, ShieldAlert, XCircle } from "lucide-react";

import type { ApprovalRequest } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

import type { ApprovalState } from "../types";

const ACTION_LABELS: Record<string, string> = {
  delete_document: "Delete document",
};

function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action.replace(/_/g, " ").replace(/^\w/, (letter) => letter.toUpperCase());
}

export function ApprovalCard({
  actions,
  state,
  disabled,
  onDecide,
}: {
  actions: ApprovalRequest[];
  state: ApprovalState;
  disabled: boolean;
  onDecide: (approved: boolean) => void;
}) {
  const submitting = state.phase === "submitting";

  if (state.phase === "resolved") {
    return (
      <div className="mb-3 flex items-center gap-2 text-sm text-muted">
        {state.approved ? (
          <CheckCircle2 className="size-4 text-success" aria-hidden />
        ) : (
          <XCircle className="size-4 text-subtle" aria-hidden />
        )}
        {state.approved ? "You approved" : "You rejected"}: {actions.map((action) => actionLabel(action.action).toLowerCase()).join(", ")}
      </div>
    );
  }

  return (
    <section
      aria-label="Approval required"
      className={cn(
        "rounded-panel border bg-surface",
        state.phase === "closed" ? "border-border" : "border-warning/30",
      )}
    >
      <header className="flex items-start gap-3 px-4 pt-4">
        <ShieldAlert className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
        <div>
          <h4 className="text-sm font-semibold">Approval required</h4>
          <p className="mt-0.5 text-sm text-muted">
            The assistant wants to take an action that can't be undone. Review it before continuing.
          </p>
        </div>
      </header>

      <ul className="mx-4 mt-3 divide-y divide-border rounded-control border border-border">
        {actions.map((action) => (
          <li key={action.tool_call_id} className="px-3 py-2.5 text-sm">
            <p className="font-medium">{actionLabel(action.action)}</p>
            <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[0.8125rem]">
              {action.source && (
                <>
                  <dt className="text-subtle">Source</dt>
                  <dd className="truncate">{action.source}</dd>
                </>
              )}
              <dt className="text-subtle">Document ID</dt>
              <dd className="truncate font-mono text-xs leading-5">{action.document_id}</dd>
            </dl>
            {!action.found && (
              <p className="mt-2 flex items-center gap-1.5 text-xs text-warning">
                <AlertTriangle className="size-3.5" aria-hidden />
                This document wasn't found in your knowledge base, so approving won't change anything.
              </p>
            )}
          </li>
        ))}
      </ul>

      <footer className="flex flex-wrap items-center justify-end gap-2 px-4 py-3.5">
        {state.phase === "closed" ? (
          <p className="mr-auto text-sm text-muted" role="status">
            {state.reason}
          </p>
        ) : (
          <>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onDecide(false)}
              disabled={disabled}
              loading={submitting && !state.approved}
            >
              Reject
            </Button>
            <Button
              size="sm"
              variant="danger"
              onClick={() => onDecide(true)}
              disabled={disabled}
              loading={submitting && state.approved}
            >
              Approve
            </Button>
          </>
        )}
      </footer>
    </section>
  );
}
