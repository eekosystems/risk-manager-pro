import { jsPDF } from "jspdf";

import {
  type Block,
  CONFIDENTIALITY_TEXT,
  type Run,
  parseBlocks,
} from "./export-markdown";


const FONT = "helvetica";

const SIZE = {
  h1: 16,
  h2: 13,
  h3: 11.5,
  body: 10.5,
  table: 9.5,
  meta: 9,
  title: 15,
} as const;

const TABLE_CELL_PAD = 4;
const TABLE_MIN_COL_WIDTH = 36;

const LINE_GAP = 1.35;

const SPACE = {
  afterTitle: 18,
  beforeH1: 14,
  beforeH2: 12,
  beforeH3: 10,
  afterHeading: 4,
  afterParagraph: 7,
  afterListItem: 2,
  afterListBlock: 6,
  hr: 8,
} as const;

const LIST_INDENT = 14;
const MARKER_GAP = 5;

function applyRunFont(doc: jsPDF, run: Run): void {
  if (run.code) {
    doc.setFont("courier", run.bold ? "bold" : "normal");
    return;
  }
  const style = run.bold && run.italic
    ? "bolditalic"
    : run.bold
      ? "bold"
      : run.italic
        ? "italic"
        : "normal";
  doc.setFont(FONT, style);
}

function wrapRuns(
  doc: jsPDF,
  runs: Run[],
  maxWidth: number,
): Run[][] {
  const lines: Run[][] = [];
  let current: Run[] = [];
  let currentWidth = 0;

  const newLine = () => {
    lines.push(current);
    current = [];
    currentWidth = 0;
  };

  for (const run of runs) {
    applyRunFont(doc, run);
    const tokens = run.text.split(/(\s+)/).filter((t) => t.length > 0);

    for (const token of tokens) {
      const tokenWidth = doc.getTextWidth(token);
      const isWhitespace = /^\s+$/.test(token);

      if (isWhitespace) {
        if (currentWidth === 0) continue;
        if (currentWidth + tokenWidth > maxWidth) continue;
        current.push({ ...run, text: token });
        currentWidth += tokenWidth;
        continue;
      }

      if (currentWidth + tokenWidth > maxWidth && currentWidth > 0) {
        newLine();
      }

      if (tokenWidth > maxWidth) {
        let chunk = "";
        let chunkWidth = 0;
        for (const ch of token) {
          const chWidth = doc.getTextWidth(ch);
          if (chunkWidth + chWidth > maxWidth && chunk.length > 0) {
            current.push({ ...run, text: chunk });
            newLine();
            chunk = ch;
            chunkWidth = chWidth;
          } else {
            chunk += ch;
            chunkWidth += chWidth;
          }
        }
        if (chunk) {
          current.push({ ...run, text: chunk });
          currentWidth = chunkWidth;
        }
        continue;
      }

      current.push({ ...run, text: token });
      currentWidth += tokenWidth;
    }
  }

  if (current.length > 0) lines.push(current);
  return lines.filter((line) => line.length > 0);
}

function trimLineWhitespace(line: Run[]): Run[] {
  const result = [...line];
  while (result.length > 0 && result[0] && /^\s+$/.test(result[0].text))
    result.shift();
  while (
    result.length > 0 &&
    result[result.length - 1] &&
    /^\s+$/.test(result[result.length - 1]!.text)
  )
    result.pop();
  return result;
}

export function exportTextToPdf(
  content: string,
  filename = `rmp-ai-response-${new Date().toISOString().slice(0, 10)}.pdf`,
): void {
  const doc = new jsPDF({ unit: "pt", format: "letter" });
  const marginX = 56;
  const marginTop = 56;
  const marginBottom = 96;
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const contentWidth = pageWidth - marginX * 2;

  let y = marginTop;
  let pageNumber = 1;

  const drawFooter = () => {
    const footerLineHeight = 9 * 1.3;
    const wrappedFooter = doc.splitTextToSize(CONFIDENTIALITY_TEXT, contentWidth);
    const blockHeight = wrappedFooter.length * footerLineHeight + 6;
    const blockTop = pageHeight - marginBottom + 4;

    doc.setDrawColor(220);
    doc.setLineWidth(0.5);
    doc.line(marginX, blockTop, pageWidth - marginX, blockTop);

    doc.setFont(FONT, "bold");
    doc.setFontSize(7.5);
    doc.setTextColor(120);
    doc.text("CONFIDENTIALITY WARNING", marginX, blockTop + 8);

    doc.setFont(FONT, "normal");
    doc.setFontSize(8);
    doc.setTextColor(110);
    let footerY = blockTop + 8 + footerLineHeight;
    for (const line of wrappedFooter) {
      doc.text(line, marginX, footerY);
      footerY += footerLineHeight;
    }

    doc.setFont(FONT, "normal");
    doc.setFontSize(SIZE.meta);
    doc.setTextColor(140);
    doc.text(
      `Page ${pageNumber}`,
      pageWidth - marginX,
      blockTop + blockHeight + 2,
      { align: "right" },
    );
    doc.setTextColor(30);
  };

  const drawConfidentialityHeader = () => {
    const lineHeight = 8 * 1.3;
    const wrapped = doc.splitTextToSize(CONFIDENTIALITY_TEXT, contentWidth);

    doc.setFont(FONT, "bold");
    doc.setFontSize(7.5);
    doc.setTextColor(120);
    doc.text("CONFIDENTIALITY WARNING", marginX, y);
    y += lineHeight;

    doc.setFont(FONT, "normal");
    doc.setFontSize(8);
    doc.setTextColor(110);
    for (const line of wrapped) {
      doc.text(line, marginX, y);
      y += lineHeight;
    }

    doc.setDrawColor(220);
    doc.setLineWidth(0.5);
    doc.line(marginX, y, pageWidth - marginX, y);
    y += SPACE.afterTitle;
    doc.setTextColor(30);
  };

  const newPage = () => {
    drawFooter();
    doc.addPage();
    pageNumber += 1;
    y = marginTop;
  };

  const ensureSpace = (needed: number) => {
    if (y + needed > pageHeight - marginBottom) newPage();
  };

  const drawLineAt = (line: Run[], startX: number, baseline: number, fontSize: number) => {
    let x = startX;
    for (const run of line) {
      applyRunFont(doc, run);
      doc.setFontSize(fontSize);
      doc.text(run.text, x, baseline);
      x += doc.getTextWidth(run.text);
    }
  };

  const drawLine = (line: Run[], startX: number, fontSize: number) => {
    drawLineAt(line, startX, y, fontSize);
  };

  const renderTable = (block: Extract<Block, { kind: "table" }>) => {
    const fontSize = SIZE.table;
    const lineHeight = fontSize * LINE_GAP;
    const allRows = block.header.length > 0 ? [block.header, ...block.rows] : block.rows;
    if (allRows.length === 0) return;
    const columnCount = Math.max(...allRows.map((row) => row.length));

    // Size columns to their widest single-line content, then scale the set to
    // the page when it overflows, holding a floor so narrow columns stay legible.
    doc.setFontSize(fontSize);
    const natural = new Array<number>(columnCount).fill(0);
    for (const row of allRows) {
      row.forEach((cell, ci) => {
        let width = 0;
        for (const run of cell) {
          applyRunFont(doc, run);
          doc.setFontSize(fontSize);
          width += doc.getTextWidth(run.text);
        }
        natural[ci] = Math.max(natural[ci] ?? 0, width + TABLE_CELL_PAD * 2);
      });
    }
    const naturalTotal = natural.reduce((a, b) => a + b, 0);
    let widths =
      naturalTotal <= contentWidth
        ? natural
        : natural.map((w) => Math.max(TABLE_MIN_COL_WIDTH, (w / naturalTotal) * contentWidth));
    const clampedTotal = widths.reduce((a, b) => a + b, 0);
    if (clampedTotal > contentWidth) {
      widths = widths.map((w) => (w / clampedTotal) * contentWidth);
    }
    const tableWidth = widths.reduce((a, b) => a + b, 0);

    const drawRow = (row: Run[][], isHeader: boolean) => {
      const wrapped = widths.map((w, ci) =>
        wrapRuns(
          doc,
          (row[ci] ?? []).map((r) => ({ ...r, bold: isHeader || r.bold })),
          w - TABLE_CELL_PAD * 2,
        ).map(trimLineWhitespace),
      );
      const lineCount = Math.max(1, ...wrapped.map((lines) => lines.length));
      const rowHeight = lineCount * lineHeight + TABLE_CELL_PAD * 2;

      if (y + rowHeight > pageHeight - marginBottom) {
        newPage();
        if (!isHeader && block.header.length > 0) drawRow(block.header, true);
      }

      if (isHeader) {
        doc.setFillColor(243, 243, 243);
        doc.rect(marginX, y, tableWidth, rowHeight, "F");
      }
      doc.setDrawColor(200);
      doc.setLineWidth(0.5);
      let x = marginX;
      widths.forEach((w, ci) => {
        doc.rect(x, y, w, rowHeight);
        let baseline = y + TABLE_CELL_PAD + fontSize;
        for (const line of wrapped[ci] ?? []) {
          drawLineAt(line, x + TABLE_CELL_PAD, baseline, fontSize);
          baseline += lineHeight;
        }
        x += w;
      });
      y += rowHeight;
    };

    if (block.header.length > 0) drawRow(block.header, true);
    for (const row of block.rows) drawRow(row, false);
    doc.setTextColor(30);
  };

  const renderRuns = (
    runs: Run[],
    fontSize: number,
    indent: number,
    firstLinePrefix: { text: string; bold: boolean } | null,
  ) => {
    doc.setFontSize(fontSize);
    const lineHeight = fontSize * LINE_GAP;
    const textX = marginX + indent;
    const maxWidth = contentWidth - indent;

    const lines = wrapRuns(doc, runs, maxWidth).map(trimLineWhitespace);
    if (lines.length === 0) lines.push([]);

    lines.forEach((line, idx) => {
      ensureSpace(lineHeight);
      if (idx === 0 && firstLinePrefix) {
        doc.setFont(FONT, firstLinePrefix.bold ? "bold" : "normal");
        doc.setFontSize(fontSize);
        const prefixX = marginX + Math.max(0, indent - LIST_INDENT + 2);
        doc.text(firstLinePrefix.text, prefixX, y);
      }
      drawLine(line, textX, fontSize);
      y += lineHeight;
    });
  };

  doc.setFont(FONT, "bold");
  doc.setFontSize(SIZE.title);
  doc.setTextColor(20);
  doc.text("Risk Manager Pro — AI Response", marginX, y);
  y += SIZE.title * LINE_GAP;

  doc.setFont(FONT, "normal");
  doc.setFontSize(SIZE.meta);
  doc.setTextColor(120);
  doc.text(new Date().toLocaleString(), marginX, y);
  y += SIZE.meta * LINE_GAP;
  doc.setTextColor(180);
  doc.setLineWidth(0.5);
  doc.line(marginX, y + 2, pageWidth - marginX, y + 2);
  y += SPACE.afterTitle;
  doc.setTextColor(30);

  // The spec requires the confidentiality warning at the header as well as the
  // footer. It previously rendered only as a repeated page footer.
  drawConfidentialityHeader();

  const blocks = parseBlocks(content);
  let prevKind: Block["kind"] | null = null;

  for (const block of blocks) {
    if (block.kind === "hr") {
      ensureSpace(SPACE.hr * 2);
      y += SPACE.hr;
      doc.setDrawColor(200);
      doc.setLineWidth(0.5);
      doc.line(marginX, y, pageWidth - marginX, y);
      y += SPACE.hr;
      prevKind = block.kind;
      continue;
    }

    if (block.kind === "h1") {
      if (prevKind !== null) y += SPACE.beforeH1;
      ensureSpace(SIZE.h1 * LINE_GAP);
      renderRuns(block.runs, SIZE.h1, 0, null);
      y += SPACE.afterHeading;
    } else if (block.kind === "h2") {
      if (prevKind !== null) y += SPACE.beforeH2;
      ensureSpace(SIZE.h2 * LINE_GAP);
      renderRuns(
        block.runs.map((r) => ({ ...r, bold: true })),
        SIZE.h2,
        0,
        null,
      );
      y += SPACE.afterHeading;
    } else if (block.kind === "h3") {
      if (prevKind !== null) y += SPACE.beforeH3;
      ensureSpace(SIZE.h3 * LINE_GAP);
      renderRuns(
        block.runs.map((r) => ({ ...r, bold: true })),
        SIZE.h3,
        0,
        null,
      );
      y += SPACE.afterHeading;
    } else if (block.kind === "ul") {
      const indent = LIST_INDENT * (block.depth + 1);
      renderRuns(block.runs, SIZE.body, indent, {
        text: "•",
        bold: false,
      });
      y += SPACE.afterListItem;
    } else if (block.kind === "ol") {
      const indent = LIST_INDENT * (block.depth + 1) + MARKER_GAP;
      renderRuns(block.runs, SIZE.body, indent, {
        text: block.marker,
        bold: false,
      });
      y += SPACE.afterListItem;
    } else if (block.kind === "table") {
      renderTable(block);
      y += SPACE.afterParagraph;
    } else {
      renderRuns(block.runs, SIZE.body, 0, null);
      y += SPACE.afterParagraph;
    }

    if (
      (prevKind === "ul" || prevKind === "ol") &&
      block.kind !== "ul" &&
      block.kind !== "ol"
    ) {
      y += SPACE.afterListBlock - SPACE.afterParagraph;
    }

    prevKind = block.kind;
  }

  drawFooter();
  doc.save(filename);
}
