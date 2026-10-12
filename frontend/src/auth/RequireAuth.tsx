import { WifiOff } from "lucide-react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { LogoMark } from "@/components/layout/Logo";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";

import { useAuth } from "./useAuth";

export function FullScreenStatus({ children }: { children: ReactNode }) {
  return <div className="flex min-h-full flex-col items-center justify-center gap-4 px-6 text-center">{children}</div>;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status, endReason, retryRestore } = useAuth();
  const location = useLocation();

  if (status === "restoring") {
    return (
      <FullScreenStatus>
        <LogoMark className="size-10" mood="thinking" />
        <Spinner className="size-5 text-muted" label="Restoring your session" />
      </FullScreenStatus>
    );
  }

  if (status === "unreachable") {
    return (
      <FullScreenStatus>
        <WifiOff className="size-6 text-muted" aria-hidden />
        <div>
          <p className="text-sm font-medium">Can't reach the server</p>
          <p className="mt-1 text-sm text-muted">Your session is saved. Check that the API is running and try again.</p>
        </div>
        <Button onClick={retryRestore}>Try again</Button>
      </FullScreenStatus>
    );
  }

  if (status !== "authenticated") {
    const from = `${location.pathname}${location.search}`;
    const search = endReason === "expired" ? "?expired=1" : "";
    return <Navigate to={`/login${search}`} replace state={{ from }} />;
  }

  return <>{children}</>;
}
