import { useState } from "react";

import { errorMessage } from "@/api/errors";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { useToast } from "@/components/ui/Toast";

import { useChatSession } from "../chat/useChatSession";

import { useHistory } from "./useHistory";

export function ClearHistoryDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { clearAll } = useHistory();
  const { closeConversation, busy } = useChatSession();
  const toast = useToast();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onConfirm() {
    setSubmitting(true);
    setError(null);
    try {
      await clearAll();
      closeConversation();
      toast.show("Chat history cleared.", "success");
      onClose();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={() => !submitting && onClose()}
      title="Clear chat history?"
      description="This permanently deletes all of your saved conversations. The assistant will also stop using them as context."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button variant="danger" onClick={() => void onConfirm()} loading={submitting} disabled={busy}>
            Delete everything
          </Button>
        </>
      }
    >
      {error && (
        <p className="text-sm text-danger" role="alert">
          {error}
        </p>
      )}
    </Dialog>
  );
}
