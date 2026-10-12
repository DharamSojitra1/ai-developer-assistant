import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Mascot } from "./Mascot";

describe("Mascot", () => {
  it("gives each instance its own gradient ids", () => {
    const { container } = render(
      <>
        <Mascot />
        <Mascot />
      </>,
    );
    const ids = [...container.querySelectorAll("radialGradient, linearGradient")].map((gradient) => gradient.id);
    expect(ids.length).toBeGreaterThan(0);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("keeps the small mascot simple and decorates the large one", () => {
    const { container: small } = render(<Mascot size="sm" />);
    expect(small.querySelector('[data-part="body"]')).toBeNull();
    expect(small.querySelector('[data-part="hands"]')).toBeNull();

    const { container: large } = render(<Mascot size="lg" />);
    expect(large.querySelector('[data-part="body"]')).not.toBeNull();
    expect(large.querySelectorAll('[data-part="hands"] .bot-hand')).toHaveLength(2);
  });

  it("smiles on hover only when interactive", () => {
    const { container, rerender } = render(<Mascot mood="idle" interactive />);
    const root = container.firstElementChild!;
    fireEvent.pointerEnter(root);
    expect(root.getAttribute("data-mood")).toBe("happy");
    fireEvent.pointerLeave(root);
    expect(root.getAttribute("data-mood")).toBe("idle");

    rerender(<Mascot mood="idle" />);
    fireEvent.pointerEnter(container.firstElementChild!);
    expect(container.firstElementChild!.getAttribute("data-mood")).toBe("idle");
  });

  it("keeps working moods on hover", () => {
    const { container } = render(<Mascot mood="thinking" interactive />);
    const root = container.firstElementChild!;
    fireEvent.pointerEnter(root);
    expect(root.getAttribute("data-mood")).toBe("thinking");
  });

  it("reflects the mood and hides itself from assistive technology", () => {
    const { container } = render(<Mascot mood="thinking" />);
    const root = container.firstElementChild!;
    expect(root.getAttribute("data-mood")).toBe("thinking");
    expect(root.getAttribute("aria-hidden")).toBe("true");
  });
});
