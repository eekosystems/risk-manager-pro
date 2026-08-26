import { describe, expect, it } from "vitest";

import { parseBlocks } from "./export-pdf";

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
