import { useState } from "react";

import { errorMessage } from "@/api/errors";
import type { ConversationSummary } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { useToast } from "@/components/ui/Toast";

import { useChatSession } from "../chat/useChatSession";

import { useHistory } from "./useHistory";

export function DeleteConversationDialog({
  conversation,
  onClose,
}: {
  conversation: ConversationSummary | null;
  onClose: () => void;
}) {
  const { remove } = useHistory();
  const { closeConversation } = useChatSession();
  const toast = useToast();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function close() {
    if (submitting) return;
    setError(null);
    onClose();
  }

  async function onConfirm() {
    if (!conversation) return;
    setSubmitting(true);
    setError(null);
    try {
      await remove(conversation.id);
      closeConversation(conversation.id);
      toast.show("Conversation deleted.", "success");
      onClose();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={conversation !== null}
      onClose={close}
      title="Delete conversation?"
      description="This permanently deletes the conversation and all of its messages."
      footer={
        <>
          <Button variant="ghost" onClick={close} disabled={submitting}>
            Cancel
          </Button>
          <Button variant="danger" onClick={() => void onConfirm()} loading={submitting}>
            Delete
          </Button>
        </>
      }
    >
      {conversation && <p className="truncate text-sm font-medium text-fg">{conversation.title || "Untitled"}</p>}
      {error && (
        <p className="mt-2 text-sm text-danger" role="alert">
          {error}
        </p>
      )}
    </Dialog>
  );
}
