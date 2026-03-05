export const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt"];

export const ALLOWED_MIME_TYPES = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
]);

export const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB

export interface ValidatedFile {
  id: string;
  name: string;
  size: string;
  file: File;
}

export interface ValidationResult {
  valid: ValidatedFile[];
  errors: string[];
}

export function validateFiles(fileList: FileList): ValidationResult {
  const valid: ValidatedFile[] = [];
  const errors: string[] = [];

  for (const f of Array.from(fileList)) {
    const ext = f.name.toLowerCase().slice(f.name.lastIndexOf("."));
    if (!ALLOWED_EXTENSIONS.includes(ext) || !ALLOWED_MIME_TYPES.has(f.type)) {
      errors.push(`"${f.name}" is not a supported file type. Allowed: PDF, DOCX, TXT`);
      continue;
    }
    if (f.size > MAX_FILE_SIZE_BYTES) {
      errors.push(`"${f.name}" exceeds the 50 MB size limit`);
      continue;
    }
    valid.push({
      id: `${Date.now()}-${Math.random()}`,
      name: f.name,
      size: `${(f.size / 1024).toFixed(1)} KB`,
      file: f,
    });
  }

  return { valid, errors };
}
