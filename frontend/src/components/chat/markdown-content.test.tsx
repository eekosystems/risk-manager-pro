import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { preprocessCitations } from "@/lib/citations";
import type { Citation } from "@/types/api";

import { MarkdownContent } from "./markdown-content";

function citation(n: number): Citation {
  return {
    source: `CSPP_Part_${n}.pdf`,
    source_type: "client",
    section: null,
    content: `chunk ${n}`,
    chunk_id: `c${n}`,
    rank: n,
    match_tier: "High",
  };
}

const CITATIONS = [1, 2, 3, 4, 5, 6, 7].map(citation);

describe("preprocessCitations", () => {
  it("links a lone source and keeps the brackets as text", () => {
    expect(preprocessCitations("See [Source 2].")).toBe(
      "See \\[[Source 2](#citation-2)\\].",
    );
  });

  it("links every source in a grouped citation", () => {
    expect(preprocessCitations("Scope [Source 1, Source 2, Source 7].")).toBe(
      "Scope \\[[Source 1](#citation-1), [Source 2](#citation-2), [Source 7](#citation-7)\\].",
    );
  });

  it("handles the plural and conjunction forms", () => {
    expect(preprocessCitations("[Sources 3 and 5]")).toBe(
      "\\[Sources [3](#citation-3) and [5](#citation-5)\\]",
    );
  });

  it("follows a group broken across a line", () => {
    expect(preprocessCitations("[Source 17,\nSource 18]")).toBe(
      "\\[[Source 17](#citation-17),\n[Source 18](#citation-18)\\]",
    );
  });

  it("leaves brackets that are not citations alone", () => {
    expect(preprocessCitations("the [Source of truth] is the CSPP [ref 4]")).toBe(
      "the [Source of truth] is the CSPP [ref 4]",
    );
  });
});

describe("MarkdownContent citations", () => {
  it("makes each source in a group its own clickable citation", async () => {
    const onCitationClick = vi.fn();
    render(
      <MarkdownContent
        content="Install lighting [Source 1, Source 2, Source 7]."
        citations={CITATIONS}
        onCitationClick={onCitationClick}
      />,
    );

    const buttons = screen.getAllByRole("button");
    expect(buttons.map((b) => b.textContent)).toEqual(["Source 1", "Source 2", "Source 7"]);

    await userEvent.click(buttons[2]!);
    expect(onCitationClick).toHaveBeenCalledWith(6);
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("shows a source number past the retrieved set as plain text, not a link", () => {
    render(
      <MarkdownContent
        content="Per the checklist [Source 9]."
        citations={CITATIONS.slice(0, 2)}
      />,
    );

    expect(screen.getByText(/Source 9/)).toBeInTheDocument();
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("renders citations as text when the message carries no citations", () => {
    render(<MarkdownContent content="Per the checklist [Source 1]." />);

    expect(screen.getByText(/\[Source 1\]/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
