import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { groupSources, SourcesPanel } from "./SourcesPanel";

describe("groupSources", () => {
  it("groups excerpts by document and drops duplicates", () => {
    const groups = groupSources([
      { document_id: "doc-1", text: "a" },
      { document_id: "doc-1", text: "a" },
      { document_id: "doc-1", text: "b" },
      { document_id: "doc-2", text: "c" },
    ]);

    expect(groups).toEqual([
      { documentId: "doc-1", excerpts: ["a", "b"] },
      { documentId: "doc-2", excerpts: ["c"] },
    ]);
  });

  it("keeps the URL and title of web sources", () => {
    const [group] = groupSources([
      { document_id: "https://example.com/a", text: "x", url: "https://example.com/a", title: "Example" },
    ]);

    expect(group).toMatchObject({ url: "https://example.com/a", title: "Example" });
  });

  it("never keeps a non-http URL", () => {
    const [group] = groupSources([{ document_id: "x", text: "x", url: "javascript:alert(1)", title: "Bad" }]);

    expect(group.url).toBeUndefined();
  });
});

describe("SourcesPanel", () => {
  it("renders web sources as external links and documents as plain IDs", () => {
    const groups = groupSources([
      { document_id: "https://docs.example.com/page", text: "web text", url: "https://docs.example.com/page", title: "Docs page" },
      { document_id: "notes-1", text: "doc text" },
    ]);

    render(<SourcesPanel id="sources" groups={groups} />);

    const link = screen.getByRole("link", { name: /Docs page/ });
    expect(link).toHaveAttribute("href", "https://docs.example.com/page");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText("docs.example.com")).toBeInTheDocument();
    expect(screen.getByText("notes-1")).toBeInTheDocument();
  });
});
