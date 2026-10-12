import { createContext, useContext } from "react";

export interface ShellContextValue {
  isDesktop: boolean;
  sidebarCollapsed: boolean;
  openSidebar: () => void;
}

export const ShellContext = createContext<ShellContextValue>({
  isDesktop: true,
  sidebarCollapsed: false,
  openSidebar: () => undefined,
});

export function useShell(): ShellContextValue {
  return useContext(ShellContext);
}
