import { lazy, Suspense } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthProvider";
import { FullScreenStatus, RequireAuth } from "./auth/RequireAuth";
import { AppShell } from "./components/layout/AppShell";
import { Spinner } from "./components/ui/Spinner";
import { ToastProvider } from "./components/ui/Toast";
import { LoginPage } from "./features/auth/LoginPage";
import { RegisterPage } from "./features/auth/RegisterPage";
import { ChatPage } from "./features/chat/ChatPage";

const KnowledgePage = lazy(() => import("./features/knowledge/KnowledgePage"));
const UsagePage = lazy(() => import("./features/usage/UsagePage"));

function PageFallback() {
  return (
    <div className="flex flex-1 items-center justify-center">
      <Spinner className="size-5 text-muted" label="Loading page" />
    </div>
  );
}

function NotFound() {
  return (
    <FullScreenStatus>
      <p className="text-sm font-medium">Page not found</p>
      <Link to="/" className="text-sm text-accent hover:underline">
        Back to chat
      </Link>
    </FullScreenStatus>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route
              element={
                <RequireAuth>
                  <AppShell />
                </RequireAuth>
              }
            >
              <Route index element={<ChatPage />} />
              <Route path="c/:conversationId" element={<ChatPage />} />
              <Route
                path="knowledge"
                element={
                  <Suspense fallback={<PageFallback />}>
                    <KnowledgePage />
                  </Suspense>
                }
              />
              <Route
                path="usage"
                element={
                  <Suspense fallback={<PageFallback />}>
                    <UsagePage />
                  </Suspense>
                }
              />
              <Route path="chat" element={<Navigate to="/" replace />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
