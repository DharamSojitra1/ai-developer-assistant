import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError, errorMessage } from "@/api/errors";
import { PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH } from "@/api/types";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/States";
import { TextField } from "@/components/ui/TextField";
import { safeRedirectPath } from "@/lib/redirect";

import { AuthLayout } from "./AuthLayout";

interface FieldErrors {
  email?: string;
  password?: string;
  confirm?: string;
}

function validate(email: string, password: string, confirm: string): FieldErrors {
  const errors: FieldErrors = {};
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) errors.email = "Enter a valid email address.";
  if (password.length < PASSWORD_MIN_LENGTH) errors.password = `Use at least ${PASSWORD_MIN_LENGTH} characters.`;
  else if (password.length > PASSWORD_MAX_LENGTH) errors.password = `Use at most ${PASSWORD_MAX_LENGTH} characters.`;
  if (confirm !== password) errors.confirm = "Passwords don't match.";
  return errors;
}

export function RegisterPage() {
  const { status, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const destination = safeRedirectPath((location.state as { from?: unknown } | null)?.from);

  if (status === "authenticated" && !submitting) return <Navigate to={destination} replace />;

  function edit(field: keyof FieldErrors, setter: (value: string) => void) {
    return (event: { target: { value: string } }) => {
      setter(event.target.value);
      if (fieldErrors[field]) setFieldErrors((current) => ({ ...current, [field]: undefined }));
    };
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting) return;

    const errors = validate(email, password, confirm);
    setFieldErrors(errors);
    setError(null);
    if (Object.keys(errors).length) return;

    setSubmitting(true);
    try {
      await register(email, password);
      navigate(destination, { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        setFieldErrors({ email: "An account with this email already exists." });
      } else {
        setError(errorMessage(caught));
      }
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Chat with the assistant and build your own knowledge base."
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" state={location.state} className="font-medium text-accent hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      {error && <ErrorState title="Couldn't create your account" message={error} className="mb-5" />}
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <TextField
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          autoFocus
          value={email}
          error={fieldErrors.email}
          onChange={edit("email", setEmail)}
        />
        <TextField
          label="Password"
          type="password"
          name="new-password"
          autoComplete="new-password"
          value={password}
          error={fieldErrors.password}
          hint={`${PASSWORD_MIN_LENGTH} to ${PASSWORD_MAX_LENGTH} characters.`}
          onChange={edit("password", setPassword)}
        />
        <TextField
          label="Confirm password"
          type="password"
          name="confirm-password"
          autoComplete="new-password"
          value={confirm}
          error={fieldErrors.confirm}
          onChange={edit("confirm", setConfirm)}
        />
        <Button type="submit" variant="primary" className="w-full" loading={submitting}>
          Create account
        </Button>
      </form>
    </AuthLayout>
  );
}
