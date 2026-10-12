import { useContext } from "react";

import { ChatSessionContext, type ChatSessionValue } from "./ChatSessionProvider";

export function useChatSession(): ChatSessionValue {
  const context = useContext(ChatSessionContext);
  if (!context) throw new Error("useChatSession must be used inside ChatSessionProvider");
  return context;
}
