import { Info } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/States";
import { TextField } from "@/components/ui/TextField";
import { safeRedirectPath } from "@/lib/redirect";

import { AuthLayout } from "./AuthLayout";

export function LoginPage() {
  const { status, login, email: savedEmail } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState(savedEmail ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const destination = safeRedirectPath((location.state as { from?: unknown } | null)?.from);
  const expired = searchParams.get("expired") === "1";

  if (status === "authenticated" && !submitting) return <Navigate to={destination} replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);

    try {
      await login(email, password);
      navigate(destination, { replace: true });
    } catch (caught) {
      setError(errorMessage(caught));
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to continue to your assistant."
      footer={
        <>
          New here?{" "}
          <Link to="/register" state={location.state} className="font-medium text-accent hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      {expired && !error && (
        <div role="status" className="mb-5 flex items-start gap-2.5 rounded-panel border border-border bg-surface px-3.5 py-3 text-sm text-muted">
          <Info className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
          Your session expired. Sign in again to pick up where you left off.
        </div>
      )}
      {error && <ErrorState title="Couldn't sign in" message={error} className="mb-5" />}
      <form onSubmit={onSubmit} className="space-y-4" noValidate={false}>
        <TextField
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          required
          autoFocus={!email}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <TextField
          label="Password"
          type="password"
          name="password"
          autoComplete="current-password"
          required
          autoFocus={Boolean(email)}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <Button type="submit" variant="primary" className="w-full" loading={submitting}>
          Sign in
        </Button>
      </form>
    </AuthLayout>
  );
}
