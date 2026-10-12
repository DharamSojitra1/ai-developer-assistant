import { describe, expect, it } from "vitest";

import { safeRedirectPath } from "./redirect";

describe("safeRedirectPath", () => {
  it("allows in-app paths", () => {
    expect(safeRedirectPath("/knowledge")).toBe("/knowledge");
    expect(safeRedirectPath("/usage?days=7")).toBe("/usage?days=7");
  });

  it("rejects external and protocol-relative destinations", () => {
    expect(safeRedirectPath("https://evil.example")).toBe("/");
    expect(safeRedirectPath("//evil.example")).toBe("/");
    expect(safeRedirectPath("/\\evil.example")).toBe("/");
    expect(safeRedirectPath(undefined)).toBe("/");
  });

  it("does not loop back to the auth pages", () => {
    expect(safeRedirectPath("/login?expired=1")).toBe("/");
  });
});
