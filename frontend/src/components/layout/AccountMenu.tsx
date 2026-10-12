import { BarChart3, ChevronsUpDown, LogOut, Trash2 } from "lucide-react";
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/useAuth";
import { ClearHistoryDialog } from "@/features/history/ClearHistoryDialog";
import { cn } from "@/lib/cn";

function MenuItem({ icon, children, onSelect, danger }: {
  icon: ReactNode;
  children: ReactNode;
  onSelect: () => void;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      tabIndex={-1}
      onClick={onSelect}
      className={cn(
        "flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm transition-colors focus:outline-none [&_svg]:size-4",
        danger ? "text-danger hover:bg-danger/10 focus:bg-danger/10" : "text-fg hover:bg-hover focus:bg-hover",
      )}
    >
      {icon}
      {children}
    </button>
  );
}

export function AccountMenu({ onNavigate }: { onNavigate?: () => void }) {
  const { email, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [clearOpen, setClearOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  const items = () => Array.from(menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);

  useEffect(() => {
    if (!open) return;
    items()[0]?.focus();

    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  function close(restoreFocus = true) {
    setOpen(false);
    if (restoreFocus) triggerRef.current?.focus();
  }

  function onMenuKeyDown(event: KeyboardEvent) {
    const list = items();
    const index = list.indexOf(document.activeElement as HTMLElement);

    if (event.key === "Escape") {
      event.preventDefault();
      close();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const delta = event.key === "ArrowDown" ? 1 : -1;
      list[(index + delta + list.length) % list.length]?.focus();
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      (event.key === "Home" ? list[0] : list[list.length - 1])?.focus();
    } else if (event.key === "Tab") {
      close(false);
    }
  }

  const initial = (email?.[0] ?? "?").toUpperCase();

  return (
    <div ref={rootRef} className="relative">
      {open && (
        <div
          ref={menuRef}
          id={menuId}
          role="menu"
          aria-label="Account"
          onKeyDown={onMenuKeyDown}
          className="absolute inset-x-0 bottom-full z-30 mb-1.5 rounded-panel border border-border bg-elevated p-1 shadow-2xl"
        >
          {email && <p className="truncate px-2.5 pb-1.5 pt-1 text-xs text-subtle">{email}</p>}
          <MenuItem
            icon={<BarChart3 />}
            onSelect={() => {
              close(false);
              navigate("/usage");
              onNavigate?.();
            }}
          >
            Usage
          </MenuItem>
          <MenuItem
            icon={<Trash2 />}
            onSelect={() => {
              close(false);
              setClearOpen(true);
            }}
          >
            Clear chat history
          </MenuItem>
          <div className="my-1 h-px bg-border" role="separator" />
          <MenuItem icon={<LogOut />} danger onSelect={() => void logout()}>
            Sign out
          </MenuItem>
        </div>
      )}
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((value) => !value)}
        onKeyDown={(event) => {
          if (event.key === "ArrowUp" || event.key === "ArrowDown") {
            event.preventDefault();
            setOpen(true);
          }
        }}
        className="flex w-full items-center gap-2.5 rounded-control px-2 py-2 text-left transition-colors hover:bg-hover"
      >
        <span
          aria-hidden
          className="flex size-7 shrink-0 items-center justify-center rounded-full bg-accent/15 text-xs font-semibold text-accent"
        >
          {initial}
        </span>
        <span className="min-w-0 flex-1 truncate text-[0.8125rem] text-fg">{email ?? "Account"}</span>
        <ChevronsUpDown className="size-4 shrink-0 text-subtle" aria-hidden />
      </button>
      <ClearHistoryDialog open={clearOpen} onClose={() => setClearOpen(false)} />
    </div>
  );
}
