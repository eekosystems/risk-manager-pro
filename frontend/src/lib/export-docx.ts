import {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  HeadingLevel,
  Packer,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} from "docx";

import {
  type Block,
  CONFIDENTIALITY_TEXT,
  type Run,
  parseBlocks,
} from "./export-markdown";

const BODY_FONT = "Calibri";
const CODE_FONT = "Consolas";

// docx sizes are in half-points, so 21 renders as 10.5pt — matching the PDF.
const SIZE = {
  title: 30,
  meta: 18,
  h1: 26,
  h2: 24,
  h3: 23,
  body: 21,
  table: 19,
  confidentiality: 16,
  confidentialityLabel: 15,
} as const;

const COLOR = {
  body: "1E1E1E",
  meta: "787878",
  muted: "6E6E6E",
  rule: "DCDCDC",
  tableBorder: "C8C8C8",
  tableHeaderFill: "F3F3F3",
} as const;

const LIST_INDENT_TWIPS = 360;

function toTextRuns(runs: Run[], overrides: Partial<Run> = {}): TextRun[] {
  return runs.map((run) => {
    const merged = { ...run, ...overrides };
    return new TextRun({
      text: merged.text,
      bold: merged.bold,
      italics: merged.italic,
      font: merged.code ? CODE_FONT : BODY_FONT,
      color: COLOR.body,
    });
  });
}

function headingParagraph(block: Extract<Block, { kind: "h1" | "h2" | "h3" }>): Paragraph {
  const level =
    block.kind === "h1"
      ? HeadingLevel.HEADING_1
      : block.kind === "h2"
        ? HeadingLevel.HEADING_2
        : HeadingLevel.HEADING_3;
  const size =
    block.kind === "h1" ? SIZE.h1 : block.kind === "h2" ? SIZE.h2 : SIZE.h3;

  return new Paragraph({
    heading: level,
    spacing: { before: block.kind === "h1" ? 280 : 240, after: 120 },
    children: block.runs.map(
      (run) =>
        new TextRun({
          text: run.text,
          bold: true,
          italics: run.italic,
          font: run.code ? CODE_FONT : BODY_FONT,
          size,
          color: COLOR.body,
        }),
    ),
  });
}

function bodyParagraph(runs: Run[]): Paragraph {
  return new Paragraph({
    spacing: { after: 140, line: 276 },
    children: toTextRuns(runs),
  });
}

function listParagraph(
  block: Extract<Block, { kind: "ul" | "ol" }>,
): Paragraph {
  // Markers are written inline rather than using Word's numbering definitions:
  // the model already emits its own numbering, and Word would renumber a list
  // that restarts partway through an answer.
  const marker = block.kind === "ul" ? "• " : `${block.marker} `;
  return new Paragraph({
    spacing: { after: 60, line: 276 },
    indent: { left: LIST_INDENT_TWIPS * (block.depth + 1) },
    children: [
      new TextRun({ text: marker, font: BODY_FONT, color: COLOR.body }),
      ...toTextRuns(block.runs),
    ],
  });
}

function horizontalRule(): Paragraph {
  return new Paragraph({
    spacing: { before: 160, after: 160 },
    border: {
      bottom: { style: BorderStyle.SINGLE, size: 6, color: COLOR.rule, space: 1 },
    },
    children: [],
  });
}

function tableCell(runs: Run[], isHeader: boolean): TableCell {
  return new TableCell({
    // Spread rather than pass undefined: exactOptionalPropertyTypes rejects it.
    ...(isHeader
      ? {
          shading: {
            type: ShadingType.CLEAR,
            fill: COLOR.tableHeaderFill,
            color: "auto",
          },
        }
      : {}),
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [
      new Paragraph({
        children: runs.length > 0
          ? runs.map(
              (run) =>
                new TextRun({
                  text: run.text,
                  bold: isHeader || run.bold,
                  italics: run.italic,
                  font: run.code ? CODE_FONT : BODY_FONT,
                  size: SIZE.table,
                  color: COLOR.body,
                }),
            )
          : [new TextRun({ text: "", font: BODY_FONT, size: SIZE.table })],
      }),
    ],
  });
}

function buildTable(block: Extract<Block, { kind: "table" }>): Table | null {
  const allRows = block.header.length > 0 ? [block.header, ...block.rows] : block.rows;
  if (allRows.length === 0) return null;
  const columnCount = Math.max(...allRows.map((row) => row.length));

  const border = { style: BorderStyle.SINGLE, size: 4, color: COLOR.tableBorder };
  const rows: TableRow[] = [];

  if (block.header.length > 0) {
    rows.push(
      new TableRow({
        // Repeat the header when a long table spills onto the next page.
        tableHeader: true,
        children: Array.from({ length: columnCount }, (_, i) =>
          tableCell(block.header[i] ?? [], true),
        ),
      }),
    );
  }

  for (const row of block.rows) {
    rows.push(
      new TableRow({
        children: Array.from({ length: columnCount }, (_, i) =>
          tableCell(row[i] ?? [], false),
        ),
      }),
    );
  }

  return new Table({
    rows,
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: border,
      bottom: border,
      left: border,
      right: border,
      insideHorizontal: border,
      insideVertical: border,
    },
  });
}

function confidentialityParagraphs(spaceAfter: number): Paragraph[] {
  return [
    new Paragraph({
      spacing: { after: 40 },
      children: [
        new TextRun({
          text: "CONFIDENTIALITY WARNING",
          bold: true,
          font: BODY_FONT,
          size: SIZE.confidentialityLabel,
          color: COLOR.meta,
        }),
      ],
    }),
    new Paragraph({
      spacing: { after: spaceAfter },
      children: [
        new TextRun({
          text: CONFIDENTIALITY_TEXT,
          font: BODY_FONT,
          size: SIZE.confidentiality,
          color: COLOR.muted,
        }),
      ],
    }),
  ];
}

/** Convert parsed blocks into the document body. */
function buildBody(content: string): (Paragraph | Table)[] {
  const children: (Paragraph | Table)[] = [
    new Paragraph({
      spacing: { after: 60 },
      children: [
        new TextRun({
          text: "Risk Manager Pro — AI Response",
          bold: true,
          font: BODY_FONT,
          size: SIZE.title,
          color: COLOR.body,
        }),
      ],
    }),
    new Paragraph({
      spacing: { after: 160 },
      border: {
        bottom: { style: BorderStyle.SINGLE, size: 6, color: COLOR.rule, space: 4 },
      },
      children: [
        new TextRun({
          text: new Date().toLocaleString(),
          font: BODY_FONT,
          size: SIZE.meta,
          color: COLOR.meta,
        }),
      ],
    }),
    // The spec requires the warning at the header as well as the footer.
    ...confidentialityParagraphs(240),
  ];

  for (const block of parseBlocks(content)) {
    if (block.kind === "hr") {
      children.push(horizontalRule());
    } else if (block.kind === "h1" || block.kind === "h2" || block.kind === "h3") {
      children.push(headingParagraph(block));
    } else if (block.kind === "ul" || block.kind === "ol") {
      children.push(listParagraph(block));
    } else if (block.kind === "table") {
      const table = buildTable(block);
      if (table) {
        children.push(table);
        // Word merges adjacent tables that are not separated by a paragraph.
        children.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
      }
    } else {
      children.push(bodyParagraph(block.runs));
    }
  }

  return children;
}

/** Build the complete Word document, footers and styles included. */
export function buildDocument(content: string): Document {
  return new Document({
    styles: {
      default: {
        document: {
          run: { font: BODY_FONT, size: SIZE.body, color: COLOR.body },
        },
      },
    },
    sections: [
      {
        properties: {
          page: { margin: { top: 1120, right: 1120, bottom: 1120, left: 1120 } },
        },
        // A real Word footer repeats the warning on every page without the
        // exporter having to paginate the content itself.
        footers: {
          default: new Footer({
            children: [
              new Paragraph({
                alignment: AlignmentType.LEFT,
                border: {
                  top: { style: BorderStyle.SINGLE, size: 6, color: COLOR.rule, space: 6 },
                },
                children: [
                  new TextRun({
                    text: "CONFIDENTIALITY WARNING",
                    bold: true,
                    font: BODY_FONT,
                    size: SIZE.confidentialityLabel,
                    color: COLOR.meta,
                  }),
                ],
              }),
              new Paragraph({
                children: [
                  new TextRun({
                    text: CONFIDENTIALITY_TEXT,
                    font: BODY_FONT,
                    size: SIZE.confidentiality,
                    color: COLOR.muted,
                  }),
                ],
              }),
            ],
          }),
        },
        children: buildBody(content),
      },
    ],
  });
}

export const DOCX_MIME =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

export function defaultDocxFilename(): string {
  return `rmp-ai-response-${new Date().toISOString().slice(0, 10)}.docx`;
}

/** Render an assistant message to a .docx file and hand it to the browser. */
export async function exportTextToDocx(
  content: string,
  filename = defaultDocxFilename(),
): Promise<void> {
  const blob = await Packer.toBlob(buildDocument(content));
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
