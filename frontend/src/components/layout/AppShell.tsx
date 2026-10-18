import { useCallback, useMemo, useState } from "react";
import { Outlet } from "react-router-dom";

import { ChatSessionProvider } from "@/features/chat/ChatSessionProvider";
import { HistoryProvider } from "@/features/history/HistoryProvider";
import { useLocalStorage } from "@/hooks/useLocalStorage";
import { useMediaQuery } from "@/hooks/useMediaQuery";

import { MobileDrawer } from "./MobileDrawer";
import { ShellContext } from "./ShellContext";
import { Sidebar } from "./Sidebar";

const isBoolean = (value: unknown): value is boolean => typeof value === "boolean";

export function AppShell() {
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const [collapsed, setCollapsed] = useLocalStorage("ada.sidebar_collapsed", false, isBoolean);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const closeDrawer = useCallback(() => setDrawerOpen(false), []);
  const openSidebar = useCallback(() => {
    if (isDesktop) setCollapsed(false);
    else setDrawerOpen(true);
  }, [isDesktop, setCollapsed]);

  const shell = useMemo(
    () => ({ isDesktop, sidebarCollapsed: collapsed, openSidebar }),
    [isDesktop, collapsed, openSidebar],
  );

  return (
    <HistoryProvider>
      <ChatSessionProvider>
        <ShellContext.Provider value={shell}>
          <a
            href="#main"
            className="sr-only z-50 rounded-control bg-accent px-3 py-2 text-sm font-medium text-accent-fg focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
          >
            Skip to content
          </a>
          <div className="flex h-dvh overflow-hidden">
            {isDesktop ? (
              !collapsed && (
                <aside className="w-[264px] shrink-0 border-r border-border bg-surface" aria-label="Sidebar">
                  <Sidebar variant="desktop" onClose={() => setCollapsed(true)} onNavigate={() => undefined} />
                </aside>
              )
            ) : (
              <MobileDrawer open={drawerOpen} onClose={closeDrawer}>
                <Sidebar variant="drawer" onClose={closeDrawer} onNavigate={closeDrawer} />
              </MobileDrawer>
            )}
            <main id="main" className="flex min-w-0 min-h-0 flex-1 flex-col overflow-hidden">
              <Outlet />
            </main>
          </div>
        </ShellContext.Provider>
      </ChatSessionProvider>
    </HistoryProvider>
  );
}
