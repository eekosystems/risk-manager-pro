import { describe, expect, it } from "vitest";

import {
  ALLOWED_EXTENSIONS,
  ALLOWED_MIME_TYPES,
  MAX_FILE_SIZE_BYTES,
  formatFileSize,
  validateFiles,
} from "./file-validation";

const XLSX_MIME =
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

function fileList(...files: File[]): FileList {
  return files as unknown as FileList;
}

function makeFile(name: string, type: string, size: number): File {
  const file = new File(["x"], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

describe("formatFileSize", () => {
  it("uses bytes below 1 KB", () => {
    expect(formatFileSize(512)).toBe("512 B");
  });

  it("steps up through KB, MB and GB", () => {
    expect(formatFileSize(2048)).toBe("2.0 KB");
    expect(formatFileSize(5 * 1024 * 1024)).toBe("5.0 MB");
    expect(formatFileSize(2 * 1024 * 1024 * 1024)).toBe("2.0 GB");
  });

  it("does not report a multi-gigabyte file in kilobytes", () => {
    // Regression: a 2 GB upload previously rendered as "2097152.0 KB".
    expect(formatFileSize(MAX_FILE_SIZE_BYTES)).toBe("2.0 GB");
  });
});

describe("validateFiles", () => {
  it("accepts spreadsheets so tracking logs upload without conversion", () => {
    expect(ALLOWED_EXTENSIONS).toContain(".xlsx");
    expect(ALLOWED_MIME_TYPES.has(XLSX_MIME)).toBe(true);

    const { valid, errors } = validateFiles(
      fileList(makeFile("Airport_Safety_Tracking.xlsx", XLSX_MIME, 4096)),
    );

    expect(errors).toHaveLength(0);
    expect(valid).toHaveLength(1);
    expect(valid[0]?.size).toBe("4.0 KB");
  });

  it("rejects unsupported types with a message naming the allowed set", () => {
    const { valid, errors } = validateFiles(
      fileList(makeFile("photo.png", "image/png", 1024)),
    );

    expect(valid).toHaveLength(0);
    expect(errors[0]).toContain("PDF, DOCX, XLSX, TXT");
  });

  it("allows a file at the 2 GB ceiling and rejects one above it", () => {
    const atLimit = makeFile("big.pdf", "application/pdf", MAX_FILE_SIZE_BYTES);
    const overLimit = makeFile(
      "bigger.pdf",
      "application/pdf",
      MAX_FILE_SIZE_BYTES + 1,
    );

    expect(validateFiles(fileList(atLimit)).valid).toHaveLength(1);

    const { valid, errors } = validateFiles(fileList(overLimit));
    expect(valid).toHaveLength(0);
    expect(errors[0]).toContain("2 GB");
  });
});
