/**
 * Shared markdown parsing for the chat-output exporters.
 *
 * The PDF and Word exporters render the same assistant message, so they parse
 * it once here into a common block model rather than each carrying its own
 * copy of the grammar.
 */

export type Run = { text: string; bold: boolean; italic: boolean; code: boolean };

export type Block =
  | { kind: "h1" | "h2" | "h3"; runs: Run[] }
  | { kind: "p"; runs: Run[] }
  | { kind: "ul"; runs: Run[]; depth: number }
  | { kind: "ol"; runs: Run[]; depth: number; marker: string }
  | { kind: "table"; header: Run[][]; rows: Run[][][] }
  | { kind: "hr" };

// Verbatim per the Core Logic Prompt's MANDATORY CONFIDENTIALITY WARNING
// section. Do not reword — the spec requires this exact text, and the previous
// wording dropped "of this output" and "to the intended recipient". The spec
// also requires it at both the header and the footer of every output.
export const CONFIDENTIALITY_TEXT =
  "This output contains information intended only for the use of the individual or entity named above. If the reader of this output is not the intended recipient or the employee or agent responsible for delivering it to the intended recipient, any dissemination, publication or copying of this output is strictly prohibited.";

function parseInlines(text: string): Run[] {
  const runs: Run[] = [];
  let i = 0;
  let buf = "";
  let bold = false;
  let italic = false;

  const flush = () => {
    if (buf) {
      runs.push({ text: buf, bold, italic, code: false });
      buf = "";
    }
  };

  while (i < text.length) {
    const ch = text[i];
    const next = text[i + 1];

    if (ch === "`") {
      flush();
      const end = text.indexOf("`", i + 1);
      if (end === -1) {
        buf += ch;
        i += 1;
        continue;
      }
      runs.push({ text: text.slice(i + 1, end), bold, italic, code: true });
      i = end + 1;
      continue;
    }

    if (ch === "*" && next === "*") {
      flush();
      bold = !bold;
      i += 2;
      continue;
    }

    if (ch === "_" && next === "_") {
      flush();
      bold = !bold;
      i += 2;
      continue;
    }

    if (ch === "*" || ch === "_") {
      // A delimiter opens when it is followed by non-space and closes when it
      // is preceded by non-space. The closing case previously required a
      // preceding space, which no emphasis run ever has, so the trailing
      // marker leaked into the output as a literal "_" or "*".
      const prev = text[i - 1];
      const canOpen = !italic && next !== undefined && !/\s/.test(next);
      const canClose = italic && prev !== undefined && !/\s/.test(prev);
      if (canOpen || canClose) {
        flush();
        italic = !italic;
        i += 1;
        continue;
      }
    }

    if (ch === "[") {
      const close = text.indexOf("]", i + 1);
      if (close !== -1 && text[close + 1] === "(") {
        const parenEnd = text.indexOf(")", close + 2);
        if (parenEnd !== -1) {
          buf += text.slice(i + 1, close);
          i = parenEnd + 1;
          continue;
        }
      }
    }

    buf += ch;
    i += 1;
  }

  flush();
  return runs.filter((r) => r.text.length > 0);
}

function classifyBlock(rawLine: string): Block | null {
  const line = rawLine.replace(/\s+$/, "");
  if (!line.trim()) return null;

  if (/^\s*[-*_]{3,}\s*$/.test(line)) return { kind: "hr" };

  const heading = /^(#{1,6})\s+(.*)$/.exec(line);
  if (heading) {
    const hashes = heading[1] ?? "";
    const text = heading[2] ?? "";
    const kind = hashes.length === 1 ? "h1" : hashes.length === 2 ? "h2" : "h3";
    return { kind, runs: parseInlines(text) };
  }

  const bullet = /^(\s*)[-*•]\s+(.*)$/.exec(line);
  if (bullet) {
    const indent = bullet[1] ?? "";
    const text = bullet[2] ?? "";
    return { kind: "ul", depth: Math.floor(indent.length / 2), runs: parseInlines(text) };
  }

  const numbered = /^(\s*)(\d+)[.)]\s+(.*)$/.exec(line);
  if (numbered) {
    const indent = numbered[1] ?? "";
    const num = numbered[2] ?? "1";
    const text = numbered[3] ?? "";
    return {
      kind: "ol",
      depth: Math.floor(indent.length / 2),
      marker: `${num}.`,
      runs: parseInlines(text),
    };
  }

  return { kind: "p", runs: parseInlines(line.trim()) };
}

// A pipe-delimited row. Leading and trailing pipes are required so an ordinary
// sentence containing "|" is never mistaken for a table.
const TABLE_ROW_RE = /^\s*\|.*\|\s*$/;
const TABLE_SEPARATOR_CELL_RE = /^:?-{2,}:?$/;

function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function isSeparatorRow(cells: string[]): boolean {
  return cells.length > 0 && cells.every((cell) => TABLE_SEPARATOR_CELL_RE.test(cell));
}

// Before/after risk tables and per-hazard scoring tables were reaching the PDF
// as one run of raw pipe characters — the rows were joined into a paragraph
// like any other consecutive lines. Consecutive pipe rows now form a table
// block; the GFM separator row marks the header when present.
function buildTable(rawRows: string[][]): Block {
  const [first, second] = rawRows;
  const hasHeader = first !== undefined && second !== undefined && isSeparatorRow(second);
  const header = hasHeader ? first : [];
  const bodyRows = (hasHeader ? rawRows.slice(2) : rawRows).filter(
    (row) => !isSeparatorRow(row),
  );
  const columnCount = Math.max(header.length, ...bodyRows.map((row) => row.length));
  const toRuns = (row: string[]): Run[][] =>
    Array.from({ length: columnCount }, (_, i) => parseInlines(row[i] ?? ""));
  return {
    kind: "table",
    header: header.length > 0 ? toRuns(header) : [],
    rows: bodyRows.map(toRuns),
  };
}

export function parseBlocks(md: string): Block[] {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let paragraph: string[] = [];

  const flushParagraph = () => {
    if (paragraph.length > 0) {
      blocks.push({ kind: "p", runs: parseInlines(paragraph.join(" ")) });
      paragraph = [];
    }
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i] ?? "";
    if (!line.trim()) {
      flushParagraph();
      continue;
    }
    if (TABLE_ROW_RE.test(line)) {
      flushParagraph();
      const rawRows: string[][] = [];
      while (i < lines.length && TABLE_ROW_RE.test(lines[i] ?? "")) {
        rawRows.push(splitTableRow(lines[i] ?? ""));
        i += 1;
      }
      i -= 1;
      blocks.push(buildTable(rawRows));
      continue;
    }
    const classified = classifyBlock(line);
    if (!classified) continue;
    if (classified.kind === "p") {
      paragraph.push(line.trim());
    } else {
      flushParagraph();
      blocks.push(classified);
    }
  }
  flushParagraph();
  return blocks;
}
