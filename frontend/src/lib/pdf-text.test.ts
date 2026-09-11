import { describe, expect, it } from "vitest";

import { toStandardFontText } from "./pdf-text";

describe("toStandardFontText", () => {
  it("replaces the non-breaking hyphens that garbled the exported PDFs", () => {
    expect(toStandardFontText("wrong\u2011turn taxiing per AC 150/5370\u20112")).toBe(
      "wrong-turn taxiing per AC 150/5370-2",
    );
  });

  it("keeps the punctuation WinAnsi can draw", () => {
    const text =
      "Risk Manager Pro — AI Response: 5×5 matrix, C2 – High • " +
      "“quoted”… §139.329";

    expect(toStandardFontText(text)).toBe(text);
  });

  it("spells out arrows and comparison symbols", () => {
    expect(toStandardFontText("Initial 3B → Residual 2B; ≥ 32 chars")).toBe(
      "Initial 3B -> Residual 2B; >= 32 chars",
    );
  });

  it("normalizes typographic spaces and drops invisible characters", () => {
    expect(toStandardFontText("14 CFR\u2009§139.329\u200B")).toBe("14 CFR §139.329");
  });

  it("folds accented letters outside Latin-1 to their base letter", () => {
    expect(toStandardFontText("Łódź")).toBe("?ódz");
  });

  it("drops emoji and marks unknown symbols visibly", () => {
    expect(toStandardFontText("Done ✅ status ✓ Ω")).toBe("Done  status [x] ?");
  });
});
