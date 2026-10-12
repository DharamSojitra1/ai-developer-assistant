export type ApiErrorCode =
  | "NETWORK_ERROR"
  | "SESSION_EXPIRED"
  | "RATE_LIMITED"
  | "VALIDATION_ERROR"
  | "HTTP_ERROR"
  | (string & {});

export class ApiError extends Error {
  readonly status: number;
  readonly code: ApiErrorCode;
  readonly retryAfterSeconds: number | null;
  readonly requestId: string | null;

  constructor(
    message: string,
    options: {
      status: number;
      code?: ApiErrorCode;
      retryAfterSeconds?: number | null;
      requestId?: string | null;
    },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code ?? "HTTP_ERROR";
    this.retryAfterSeconds = options.retryAfterSeconds ?? null;
    this.requestId = options.requestId ?? null;
  }
}

const STATUS_MESSAGES: Record<number, string> = {
  400: "The request could not be processed.",
  401: "Your session has expired. Please sign in again.",
  403: "You don't have permission to do that.",
  404: "The requested resource was not found.",
  409: "That conflicts with existing data.",
  413: "The request is too large.",
  422: "Some of the submitted values are invalid.",
  429: "You're sending requests too quickly. Please wait a moment and try again.",
  500: "An unexpected error occurred. Please try again.",
  502: "The AI service is temporarily unavailable. Please try again.",
  503: "The service is temporarily unavailable. Please try again shortly.",
  504: "The AI provider took too long to respond. Please try again.",
};

/** Safe, fixed messages for server-side error codes that need specific advice. */
const CODE_MESSAGES: Record<string, string> = {
  MODEL_RATE_LIMITED: "The AI model is at its free-tier limit. Wait a few seconds and try again.",
};

function fallbackMessage(status: number): string {
  if (STATUS_MESSAGES[status]) return STATUS_MESSAGES[status];
  return status >= 500 ? STATUS_MESSAGES[500] : "The request failed.";
}

interface ValidationIssue {
  loc?: unknown[];
  msg?: string;
}

function formatValidationIssue(issue: ValidationIssue): string | null {
  if (typeof issue?.msg !== "string") return null;

  const message = issue.msg.replace(/^Value error,\s*/i, "");
  const field = Array.isArray(issue.loc)
    ? issue.loc.filter((part) => part !== "body" && typeof part === "string").join(".")
    : "";

  return field ? `${field}: ${message}` : message;
}

function parseRetryAfter(headers: Headers | undefined): number | null {
  const value = headers?.get("Retry-After");
  if (!value) return null;
  const seconds = Number(value);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : null;
}

/**
 * Normalizes the backend's error shapes:
 * `{detail: string}` (HTTPException), `{detail: [...]}` (422 validation),
 * `{success: false, error: {code, message}}` (AppException and app handlers),
 * and `{error: string}` (slowapi rate limits).
 */
export function normalizeApiError(status: number, body: unknown, headers?: Headers): ApiError {
  const retryAfterSeconds = parseRetryAfter(headers);
  const headerRequestId = headers?.get("X-Request-ID") ?? null;

  if (status === 429) {
    return new ApiError(STATUS_MESSAGES[429], { status, code: "RATE_LIMITED", retryAfterSeconds, requestId: headerRequestId });
  }

  if (body && typeof body === "object") {
    const record = body as Record<string, unknown>;
    const requestId = typeof record.request_id === "string" ? record.request_id : headerRequestId;

    // Server-side failures may describe internals, so only their code is kept.
    if (status >= 500) {
      const code = record.error && typeof record.error === "object" ? (record.error as Record<string, unknown>).code : undefined;
      const known = typeof code === "string" ? CODE_MESSAGES[code] : undefined;
      return new ApiError(known ?? fallbackMessage(status), {
        status,
        code: typeof code === "string" ? code : undefined,
        retryAfterSeconds,
        requestId,
      });
    }

    if (typeof record.detail === "string" && record.detail.trim()) {
      return new ApiError(record.detail, { status, retryAfterSeconds, requestId });
    }

    if (Array.isArray(record.detail)) {
      const messages = (record.detail as ValidationIssue[])
        .map(formatValidationIssue)
        .filter((message): message is string => Boolean(message));

      return new ApiError(messages[0] ?? STATUS_MESSAGES[422], {
        status,
        code: "VALIDATION_ERROR",
        retryAfterSeconds,
        requestId,
      });
    }

    if (record.error && typeof record.error === "object") {
      const error = record.error as Record<string, unknown>;
      const message = typeof error.message === "string" && error.message ? error.message : fallbackMessage(status);
      const code = typeof error.code === "string" ? error.code : undefined;
      return new ApiError(message, { status, code, retryAfterSeconds, requestId });
    }
  }

  return new ApiError(fallbackMessage(status), { status, retryAfterSeconds, requestId: headerRequestId });
}

export function networkError(): ApiError {
  return new ApiError("Can't reach the server. Check your connection and try again.", {
    status: 0,
    code: "NETWORK_ERROR",
  });
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Something unexpected happened. Please try again.";
}
