import { useCallback, useRef, useState } from "react";
import { clsx } from "clsx";
import { FileText, Loader2, Upload } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { useDocuments, useUploadDocument } from "@/hooks/use-documents";
import { validateFiles } from "@/lib/file-validation";

export function RecentDocuments() {
  const {
    data: documents = [],
    isLoading,
    isError,
  } = useDocuments();

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
    <>
      <h3 className="mb-3 mt-6 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-900">
        <FileText size={12} />
        Recent Documents
      </h3>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.txt"
        multiple
        className="hidden"
        onChange={handleFileChange}
      />

      <div className="mb-6 flex flex-col gap-1.5">
        {isLoading && (
          <div className="flex flex-col gap-2 px-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={`doc-skeleton-${i}`} className="flex items-center gap-2">
                <Skeleton className="h-4 w-4 shrink-0" />
                <Skeleton className="h-4 flex-1" />
                <Skeleton className="h-3 w-12" />
              </div>
            ))}
          </div>
        )}

        {isError && (
          <p className="px-2 text-xs text-red-500">
            Failed to load documents
          </p>
        )}

        {!isLoading && !isError && documents.length === 0 && (
          <button
            type="button"
            onClick={handleClick}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={clsx(
              "flex flex-col items-center gap-2 rounded-lg border-2 border-dashed px-4 py-6 text-center transition-colors",
              isDragOver
                ? "border-brand-400 bg-brand-50"
                : "border-gray-200 bg-gray-50 hover:border-brand-300 hover:bg-brand-50/50",
            )}
          >
            {isUploading ? (
              <Loader2 size={24} className="animate-spin text-brand-500" />
            ) : (
              <Upload
                size={24}
                className={clsx(
                  isDragOver ? "text-brand-500" : "text-gray-400",
                )}
              />
            )}
            <span className="text-xs font-medium text-gray-500">
              {isUploading
                ? "Uploading..."
                : isDragOver
                  ? "Drop files here"
                  : "Drop files here or click to upload"}
            </span>
            <span className="text-[10px] text-gray-400">
              PDF, DOCX, TXT (max 50 MB)
            </span>
          </button>
        )}

        {!isLoading &&
          !isError &&
          documents.length > 0 && (
            <>
              {documents.slice(0, 5).map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-gray-50"
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50">
                    <FileText size={14} className="text-brand-500" />
                  </div>
                  <div className="flex flex-1 flex-col overflow-hidden">
                    <span className="truncate text-[12px] font-medium text-gray-700">
                      {doc.filename}
                    </span>
                    <span className="text-[11px] text-gray-400">
                      {doc.status === "indexed" ? "Indexed" : doc.status}
                    </span>
                  </div>
                </div>
              ))}

              {/* Drop zone below existing docs */}
              <button
                type="button"
                onClick={handleClick}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={clsx(
                  "mt-2 flex items-center justify-center gap-1.5 rounded-lg border-2 border-dashed px-3 py-2.5 text-center transition-colors",
                  isDragOver
                    ? "border-brand-400 bg-brand-50"
                    : "border-gray-200 hover:border-brand-300 hover:bg-brand-50/50",
                )}
              >
                {isUploading ? (
                  <Loader2 size={14} className="animate-spin text-brand-500" />
                ) : (
                  <Upload
                    size={14}
                    className={clsx(
                      isDragOver ? "text-brand-500" : "text-gray-400",
                    )}
                  />
                )}
                <span className="text-[11px] font-medium text-gray-400">
                  {isUploading ? "Uploading..." : "Drop or click to add"}
                </span>
              </button>
            </>
          )}

        {uploadErrors.length > 0 && (
          <div className="mt-1 flex flex-col gap-0.5">
            {uploadErrors.map((err) => (
              <p key={err} className="text-[11px] text-red-500">{err}</p>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
