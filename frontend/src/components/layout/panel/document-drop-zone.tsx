import { useCallback, useRef, useState } from "react";
import { clsx } from "clsx";
import { Loader2, Upload } from "lucide-react";

import { useUploadDocument } from "@/hooks/use-documents";
import { validateFiles } from "@/lib/file-validation";

export function DocumentDropZone() {
  const uploadMutation = useUploadDocument();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadErrors, setUploadErrors] = useState<string[]>([]);

  const handleFiles = useCallback(
    (fileList: FileList) => {
      setUploadErrors([]);
      const { valid, errors } = validateFiles(fileList);
      if (errors.length > 0) {
        setUploadErrors(errors);
      }
      for (const vf of valid) {
        uploadMutation.mutate({ file: vf.file });
      }
    },
    [uploadMutation],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);
      if (e.dataTransfer.files.length > 0) {
        handleFiles(e.dataTransfer.files);
      }
    },
    [handleFiles],
  );

  const handleClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFiles(e.target.files);
        e.target.value = "";
      }
    },
    [handleFiles],
  );

  const isUploading = uploadMutation.isPending;

  return (
    <div className="flex flex-col gap-1.5">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.txt"
        multiple
        className="hidden"
        onChange={handleFileChange}
      />

      <button
        type="button"
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={clsx(
          "flex flex-col items-center gap-1.5 rounded-lg border-2 border-dashed px-3 py-4 text-center transition-colors",
          isDragOver
            ? "border-brand-400 bg-brand-50"
            : "border-gray-200 bg-gray-50 hover:border-brand-300 hover:bg-brand-50/50",
        )}
      >
        {isUploading ? (
          <Loader2 size={18} className="animate-spin text-brand-500" />
        ) : (
          <Upload
            size={18}
            className={clsx(isDragOver ? "text-brand-500" : "text-gray-400")}
          />
        )}
        <span className="text-[11px] font-medium text-gray-500">
          {isUploading
            ? "Uploading..."
            : isDragOver
              ? "Drop files here"
              : "Drop files or click to upload"}
        </span>
        <span className="text-[10px] text-gray-400">PDF, DOCX, TXT (max 50 MB)</span>
      </button>

      {uploadErrors.length > 0 && (
        <div className="flex flex-col gap-0.5">
          {uploadErrors.map((err) => (
            <p key={err} className="text-[11px] text-red-500">
              {err}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
