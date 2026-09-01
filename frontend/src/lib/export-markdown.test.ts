import { describe, expect, it } from "vitest";

import { parseBlocks } from "./export-markdown";

const cellText = (cell: { text: string }[]) => cell.map((r) => r.text).join("");

describe("parseBlocks tables", () => {
  it("turns consecutive pipe rows into a table with a header", () => {
    const md = [
      "Before/After Table",
      "| Stage | L | S | Cell | Band |",
      "|-------|---|---|------|------|",
      "| Initial | C | 2 | C2 | High |",
      "| Residual | D | 2 | D2 | Medium |",
    ].join("\n");

    const blocks = parseBlocks(md);

    expect(blocks.map((b) => b.kind)).toEqual(["p", "table"]);
    const table = blocks[1];
    if (table?.kind !== "table") throw new Error("expected a table block");
    expect(table.header.map(cellText)).toEqual(["Stage", "L", "S", "Cell", "Band"]);
    expect(table.rows.map((row) => row.map(cellText))).toEqual([
      ["Initial", "C", "2", "C2", "High"],
      ["Residual", "D", "2", "D2", "Medium"],
    ]);
  });

  it("keeps a table without a separator row as body rows", () => {
    const blocks = parseBlocks("| a | b |\n| c | d |");

    const table = blocks[0];
    if (table?.kind !== "table") throw new Error("expected a table block");
    expect(table.header).toEqual([]);
    expect(table.rows.map((row) => row.map(cellText))).toEqual([
      ["a", "b"],
      ["c", "d"],
    ]);
  });

  it("pads ragged rows to the widest row", () => {
    const blocks = parseBlocks("| a | b | c |\n|---|---|---|\n| only |");

    const table = blocks[0];
    if (table?.kind !== "table") throw new Error("expected a table block");
    expect(table.rows[0]?.map(cellText)).toEqual(["only", "", ""]);
  });

  it("does not mistake a sentence containing a pipe for a table", () => {
    const blocks = parseBlocks("Likelihood C | Severity 2 is a Medium band.");

    expect(blocks.map((b) => b.kind)).toEqual(["p"]);
  });

  it("ends the table at the first non-pipe line", () => {
    const blocks = parseBlocks("| a |\n|---|\n| b |\nALARP: Acceptable with conditions.");

    expect(blocks.map((b) => b.kind)).toEqual(["table", "p"]);
  });
});

describe("parseBlocks emphasis", () => {
  const runsOf = (md: string) => {
    const block = parseBlocks(md)[0];
    if (block?.kind !== "p") throw new Error("expected a paragraph block");
    return block.runs;
  };

  it("closes an underscore emphasis run instead of leaking the marker", () => {
    // Regression: the closing delimiter required a preceding space, so
    // "_low visibility_" reached the export as "low visibility_" in italics
    // that never turned off.
    const runs = runsOf("Risk during _low visibility_ operations.");

    expect(runs.map((r) => r.text).join("")).toBe(
      "Risk during low visibility operations.",
    );
    expect(runs.find((r) => r.text === "low visibility")?.italic).toBe(true);
    expect(runs[runs.length - 1]?.italic).toBe(false);
  });

  it("closes an asterisk emphasis run", () => {
    const runs = runsOf("An *urgent* hazard.");

    expect(runs.map((r) => r.text).join("")).toBe("An urgent hazard.");
    expect(runs.find((r) => r.text === "urgent")?.italic).toBe(true);
    expect(runs[runs.length - 1]?.italic).toBe(false);
  });

  it("keeps bold and italic separate", () => {
    const runs = runsOf("A **critical** and _urgent_ hazard.");

    expect(runs.map((r) => r.text).join("")).toBe("A critical and urgent hazard.");
    expect(runs.find((r) => r.text === "critical")?.bold).toBe(true);
    expect(runs.find((r) => r.text === "critical")?.italic).toBe(false);
    expect(runs.find((r) => r.text === "urgent")?.italic).toBe(true);
    expect(runs.find((r) => r.text === "urgent")?.bold).toBe(false);
  });

  it("leaves a standalone asterisk alone", () => {
    const runs = runsOf("Score 5 * 3 for the composite index.");

    expect(runs.map((r) => r.text).join("")).toBe(
      "Score 5 * 3 for the composite index.",
    );
    expect(runs.every((r) => !r.italic)).toBe(true);
  });

  it("does not italicise an unmatched trailing marker", () => {
    const runs = runsOf("Cleared for takeoff_");

    expect(runs.map((r) => r.text).join("")).toBe("Cleared for takeoff_");
  });
});
