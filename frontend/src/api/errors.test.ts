import { describe, expect, it } from "vitest";

import { normalizeApiError } from "./errors";

describe("normalizeApiError", () => {
  it("uses the detail string of an HTTPException", () => {
    const error = normalizeApiError(409, { detail: "Email already registered" });
    expect(error.message).toBe("Email already registered");
    expect(error.status).toBe(409);
  });

  it("formats the first validation issue of a 422", () => {
    const error = normalizeApiError(422, {
      detail: [{ loc: ["body", "message"], msg: "Value error, Message cannot be Empty or Whitespace" }],
    });
    expect(error.code).toBe("VALIDATION_ERROR");
    expect(error.message).toBe("message: Message cannot be Empty or Whitespace");
  });

  it("reads the AppException envelope, its code, and the request ID", () => {
    const headers = new Headers({ "Retry-After": "5" });
    const error = normalizeApiError(
      503,
      { success: false, error: { code: "DATABASE_UNAVAILABLE", message: "Try again shortly." }, request_id: "req-1" },
      headers,
    );
    expect(error.code).toBe("DATABASE_UNAVAILABLE");
    expect(error.message).toMatch(/temporarily unavailable/);
    expect(error.requestId).toBe("req-1");
    expect(error.retryAfterSeconds).toBe(5);
  });

  it("replaces slowapi's rate limit text with a friendly message", () => {
    const error = normalizeApiError(429, { error: "Rate limit exceeded: 5 per 1 minute" });
    expect(error.code).toBe("RATE_LIMITED");
    expect(error.message).toMatch(/too quickly/);
  });

  it("never surfaces server-side error details", () => {
    const error = normalizeApiError(500, { detail: "pymongo.errors.ServerSelectionTimeoutError: mongo:27017" });
    expect(error.message).not.toMatch(/mongo/);
    expect(error.message).toMatch(/unexpected error/);
  });

  it("falls back to a status message for unknown bodies", () => {
    expect(normalizeApiError(502, null).message).toMatch(/temporarily unavailable/);
    expect(normalizeApiError(500, "<html>").message).toMatch(/unexpected error/);
  });
});
