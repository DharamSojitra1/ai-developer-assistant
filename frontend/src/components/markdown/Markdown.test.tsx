import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown } from "./Markdown";

describe("Markdown", () => {
  it("renders headings, lists, and highlighted code with a copy action", () => {
    const { container } = render(<Markdown content={"## Title\n\n- one\n- two\n\n```python\nprint('hi')\n```"} />);

    expect(screen.getByRole("heading", { level: 2, name: "Title" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("python")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy code" })).toBeInTheDocument();
    expect(container.querySelector("code.hljs")).not.toBeNull();
  });

  it("does not render raw HTML from model output", () => {
    const { container } = render(<Markdown content={'<img src=x onerror="alert(1)"><script>alert(1)</script>text'} />);

    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
  });

  it("never loads remote images", () => {
    const { container } = render(<Markdown content={"![secret](https://tracker.example/p.png?d=1)"} />);

    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByRole("link", { name: "Image: secret" })).toHaveAttribute("rel", "noopener noreferrer nofollow");
  });

  it("strips javascript: URLs and opens links safely", () => {
    render(<Markdown content={"[bad](javascript:alert(1)) [good](https://example.com)"} />);

    expect(screen.getByText("bad").getAttribute("href") ?? "").not.toMatch(/javascript/i);
    const good = screen.getByRole("link", { name: "good" });
    expect(good).toHaveAttribute("target", "_blank");
    expect(good).toHaveAttribute("rel", "noopener noreferrer nofollow");
  });
});
