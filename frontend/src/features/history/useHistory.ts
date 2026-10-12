import { useContext } from "react";

import { HistoryContext, type HistoryContextValue } from "./HistoryProvider";

export function useHistory(): HistoryContextValue {
  const context = useContext(HistoryContext);
  if (!context) throw new Error("useHistory must be used inside HistoryProvider");
  return context;
}
