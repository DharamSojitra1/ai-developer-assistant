import { BarChart3, Library, MessageSquare, PanelLeftClose, SquarePen, X } from "lucide-react";
import type { ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { conversationPath } from "@/features/chat/paths";
import { useChatSession } from "@/features/chat/useChatSession";
import { HistoryList } from "@/features/history/HistoryList";
import { cn } from "@/lib/cn";

import { Button } from "../ui/Button";
import { IconButton } from "../ui/IconButton";

import { AccountMenu } from "./AccountMenu";
import { Logo } from "./Logo";

function NavItem({
  to,
  active,
  icon,
  children,
  onNavigate,
}: {
  to: string;
  /** Overrides NavLink's URL matching. */
  active?: boolean;
  icon: ReactNode;
  children: ReactNode;
  onNavigate: () => void;
}) {
  return (
    <NavLink
      to={to}
      end
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2.5 rounded-control px-3 py-2 text-[0.8125rem] transition-colors [&_svg]:size-4",
          (active ?? isActive) ? "bg-hover text-fg" : "text-muted hover:bg-hover/70 hover:text-fg",
        )
      }
    >
      {icon}
      {children}
    </NavLink>
  );
}

export function Sidebar({ variant, onClose, onNavigate }: {
  variant: "desktop" | "drawer";
  onClose: () => void;
  onNavigate: () => void;
}) {
  const { newChat, conversationId } = useChatSession();
  const { pathname } = useLocation();
  const onChatPage = pathname === "/" || pathname.startsWith("/c/");

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-14 shrink-0 items-center justify-between pl-4 pr-2">
        <Logo />
        <IconButton
          label={variant === "desktop" ? "Hide sidebar" : "Close menu"}
          icon={variant === "desktop" ? <PanelLeftClose /> : <X />}
          onClick={onClose}
        />
      </div>

      <div className="space-y-1 px-2.5 pb-3">
        <Button
          className="mb-2 w-full justify-start"
          icon={<SquarePen className="size-4" />}
          onClick={() => {
            newChat();
            onNavigate();
          }}
        >
          New chat
        </Button>
        <NavItem
          to={conversationId ? conversationPath(conversationId) : "/"}
          active={onChatPage}
          icon={<MessageSquare />}
          onNavigate={onNavigate}
        >
          Chat
        </NavItem>
        <NavItem to="/knowledge" icon={<Library />} onNavigate={onNavigate}>
          Knowledge base
        </NavItem>
        <NavItem to="/usage" icon={<BarChart3 />} onNavigate={onNavigate}>
          Usage
        </NavItem>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto border-t border-border px-1.5 pt-3">
        <h2 className="px-3 pb-2 text-xs font-medium text-muted">Recent</h2>
        <HistoryList activeId={onChatPage ? conversationId : null} onNavigate={onNavigate} />
      </div>

      <div className="shrink-0 border-t border-border p-2">
        <AccountMenu onNavigate={onNavigate} />
      </div>
    </div>
  );
}
