import { Menu, PanelLeftOpen, SquarePen } from "lucide-react";
import type { ReactNode } from "react";

import { useChatSession } from "@/features/chat/useChatSession";
import { cn } from "@/lib/cn";

import { IconButton } from "../ui/IconButton";

import { useShell } from "./ShellContext";

/** Page header; adds the menu and new-chat controls when the sidebar is hidden. */
export function TopBar({ children, className }: { children?: ReactNode; className?: string }) {
  const { isDesktop, sidebarCollapsed, openSidebar } = useShell();
  const { newChat } = useChatSession();
  const sidebarHidden = !isDesktop || sidebarCollapsed;

  return (
    <header className={cn("flex h-14 shrink-0 items-center gap-1 px-2 sm:px-3", className)}>
      {sidebarHidden && (
        <>
          <IconButton
            label={isDesktop ? "Show sidebar" : "Open menu"}
            icon={isDesktop ? <PanelLeftOpen /> : <Menu />}
            onClick={openSidebar}
          />
          <IconButton label="New chat" icon={<SquarePen />} onClick={newChat} />
        </>
      )}
      <div className="flex min-w-0 flex-1 items-center gap-2">{children}</div>
    </header>
  );
}
