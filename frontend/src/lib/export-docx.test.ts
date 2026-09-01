import { Packer } from "docx";
import JSZip from "jszip";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CONFIDENTIALITY_TEXT } from "./export-markdown";

import {
  DOCX_MIME,
  buildDocument,
  defaultDocxFilename,
  exportTextToDocx,
} from "./export-docx";

/**
 * Round-trip the exporter through a real .docx and read the parts back out, so
 * these assertions cover the file Word actually opens rather than the builder's
 * intermediate objects.
 */
async function renderParts(content: string): Promise<Record<string, string>> {
  const buffer = await Packer.toBuffer(buildDocument(content));
  const zip = await JSZip.loadAsync(buffer);
  const parts: Record<string, string> = {};
  for (const name of Object.keys(zip.files)) {
    const file = zip.file(name);
    if (file && name.endsWith(".xml")) {
      parts[name] = await file.async("string");
    }
  }
  return parts;
}

async function renderDocumentXml(content: string): Promise<string> {
  const parts = await renderParts(content);
  return parts["word/document.xml"] ?? "";
}

/** Text content of the document part with XML tags stripped. */
function visibleText(xml: string): string {
  return xml
    .replace(/<w:t[^>]*>/g, "")
    .replace(/<\/w:t>/g, "")
    .replace(/<[^>]+>/g, "");
}

describe("buildDocument", () => {
  it("includes the title and the assistant content", async () => {
    const xml = await renderDocumentXml("The runway incursion risk is Medium.");
    const text = visibleText(xml);

    expect(text).toContain("Risk Manager Pro");
    expect(text).toContain("The runway incursion risk is Medium.");
  });

  it("renders the confidentiality warning verbatim in the body header", async () => {
    const text = visibleText(await renderDocumentXml("Body text."));

    expect(text).toContain("CONFIDENTIALITY WARNING");
    expect(text).toContain(CONFIDENTIALITY_TEXT);
  });

  it("renders a markdown table as a real Word table with a repeating header", async () => {
    const md = [
      "| Stage | Cell | Band |",
      "|-------|------|------|",
      "| Initial | C2 | High |",
      "| Residual | D2 | Medium |",
    ].join("\n");

    const xml = await renderDocumentXml(md);

    expect(xml).toContain("<w:tbl>");
    // tblHeader is what makes the header row repeat across a page break.
    expect(xml).toContain("<w:tblHeader");
    const text = visibleText(xml);
    expect(text).toContain("Stage");
    expect(text).toContain("Residual");
    expect(text).toContain("Medium");
  });

  it("pads a ragged table row so every row has the same cell count", async () => {
    const xml = await renderDocumentXml("| a | b | c |\n|---|---|---|\n| only |");

    const rows = xml.match(/<w:tr[ >]/g) ?? [];
    expect(rows).toHaveLength(2);
    const cells = xml.match(/<w:tc>/g) ?? [];
    expect(cells).toHaveLength(6);
  });

  it("carries bold and italic markdown through as run formatting", async () => {
    const xml = await renderDocumentXml("A **critical** and _urgent_ hazard.");

    expect(xml).toContain("<w:b ");
    expect(xml).toContain("<w:i ");
    const text = visibleText(xml);
    expect(text).toContain("A critical and urgent hazard.");
    // The emphasis markers must be consumed, not carried through as literals.
    expect(text).not.toContain("_");
    expect(text).not.toContain("**");
  });

  it("writes list markers inline so Word does not renumber the model's list", async () => {
    const text = visibleText(await renderDocumentXml("1. First\n2. Second\n- Bullet"));

    expect(text).toContain("1.");
    expect(text).toContain("2.");
    expect(text).toContain("First");
    expect(text).toContain("•");
    expect(text).toContain("Bullet");
  });

  it("renders headings at their Word heading levels", async () => {
    const xml = await renderDocumentXml("# Findings\n\n## Detail");

    expect(xml).toContain('w:val="Heading1"');
    expect(xml).toContain('w:val="Heading2"');
  });

  it("repeats the confidentiality warning in the Word page footer", async () => {
    // The spec requires the warning at the header and the footer of every
    // output. A real Word footer part is what makes it repeat per page.
    const parts = await renderParts("Body text.");
    const footerName = Object.keys(parts).find((n) => /word\/footer\d*\.xml/.test(n));

    expect(footerName).toBeDefined();
    expect(visibleText(parts[footerName as string] ?? "")).toContain(
      CONFIDENTIALITY_TEXT,
    );
  });

  it("produces a valid docx package with the required parts", async () => {
    const parts = await renderParts("Content.");

    expect(Object.keys(parts)).toContain("word/document.xml");
    expect(Object.keys(parts)).toContain("[Content_Types].xml");
  });
});

describe("exportTextToDocx", () => {
  const click = vi.fn();

  beforeEach(() => {
    vi.restoreAllMocks();
    click.mockClear();
    URL.createObjectURL = vi.fn(() => "blob:mock");
    URL.revokeObjectURL = vi.fn();
    // jsdom does not implement navigation, so intercept the anchor click.
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(click);
  });

  it("downloads a .docx blob under the given filename", async () => {
    const anchors: HTMLAnchorElement[] = [];
    const originalCreate = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      const el = originalCreate(tag);
      if (tag === "a") anchors.push(el as HTMLAnchorElement);
      return el;
    });

    await exportTextToDocx("Some content.", "report.docx");

    expect(anchors).toHaveLength(1);
    expect(anchors[0]?.download).toBe("report.docx");
    expect(click).toHaveBeenCalledOnce();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock");
  });

  it("hands the browser a Word blob, not a generic one", async () => {
    let captured: Blob | null = null;
    URL.createObjectURL = vi.fn((blob: Blob) => {
      captured = blob;
      return "blob:mock";
    }) as unknown as typeof URL.createObjectURL;

    await exportTextToDocx("Some content.");

    expect(captured).not.toBeNull();
    expect((captured as unknown as Blob).type).toBe(DOCX_MIME);
    expect((captured as unknown as Blob).size).toBeGreaterThan(0);
  });

  it("defaults to a dated filename", () => {
    const today = new Date().toISOString().slice(0, 10);

    expect(defaultDocxFilename()).toBe(`rmp-ai-response-${today}.docx`);
  });
});
