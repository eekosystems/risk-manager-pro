import { jsPDF } from "jspdf";

function stripMarkdown(text: string): string {
  return text
    .replace(/`([^`]*)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/^#+\s+/gm, "")
    .replace(/^\s*[-*]\s+/gm, "• ")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
}

export function exportTextToPdf(
  content: string,
  filename = `rmp-ai-response-${new Date().toISOString().slice(0, 10)}.pdf`,
): void {
  const doc = new jsPDF({ unit: "pt", format: "letter" });
  const marginX = 56;
  const marginY = 56;
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const maxWidth = pageWidth - marginX * 2;
  const lineHeight = 14;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(14);
  doc.text("Risk Manager Pro — AI Response", marginX, marginY);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(120);
  doc.text(new Date().toLocaleString(), marginX, marginY + 16);

  doc.setTextColor(30);
  doc.setFontSize(11);
  const lines = doc.splitTextToSize(stripMarkdown(content), maxWidth);
  let y = marginY + 44;
  for (const line of lines) {
    if (y > pageHeight - marginY) {
      doc.addPage();
      y = marginY;
    }
    doc.text(line, marginX, y);
    y += lineHeight;
  }

  doc.save(filename);
}
