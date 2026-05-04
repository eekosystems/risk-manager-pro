import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { clsx } from "clsx";
import {
  CheckCircle2,
  FileText,
  Loader2,
  Upload,
  XCircle,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { useDocuments, useUploadDocument } from "@/hooks/use-documents";
import { useOrganizationContext } from "@/hooks/use-organization-context";
import { MAX_FILE_SIZE_LABEL, validateFiles } from "@/lib/file-validation";
import { logger } from "@/lib/logger";
import type { DocumentItem, DocumentStatus } from "@/types/api";

type Stage = "in-progress" | "success" | "failed" | "duplicate";

interface InFlight {
  key: string;
  filename: string;
  failed: boolean;
  duplicate: boolean;
  errorMessage: string | null;
}

function extractErrorMessage(err: unknown): {
  status: number | null;
  code: string | null;
  message: string | null;
} {
  if (!err || typeof err !== "object") {
    return { status: null, code: null, message: null };
  }
  const candidate = err as {
    response?: {
      status?: number;
      data?: { error?: { code?: string; message?: string } };
    };
  };
  const status = candidate.response?.status ?? null;
  const code = candidate.response?.data?.error?.code ?? null;
  const message = candidate.response?.data?.error?.message ?? null;
  return { status, code, message };
}

const STORAGE_PREFIX = "rmp.uploadedDocs.";

function storageKey(orgId: string): string {
  return `${STORAGE_PREFIX}${orgId}`;
}

function readUploadedIds(orgId: string): string[] {
  try {
    const raw = window.localStorage.getItem(storageKey(orgId));
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((v): v is string => typeof v === "string");
  } catch (err) {
    logger.warn("Failed to read uploaded doc ids from localStorage", err);
    return [];
  }
}

function writeUploadedIds(orgId: string, ids: string[]): void {
  try {
    window.localStorage.setItem(storageKey(orgId), JSON.stringify(ids));
  } catch (err) {
    logger.warn("Failed to persist uploaded doc ids to localStorage", err);
  }
}

function indexStageFor(status: DocumentStatus): Stage {
  switch (status) {
    case "indexed":
      return "success";
    case "failed":
      return "failed";
    case "uploaded":
    case "processing":
    default:
      return "in-progress";
  }
}

function StageIcon({ stage }: { stage: Stage }) {
  if (stage === "success") {
    return <CheckCircle2 size={12} className="text-green-600" />;
  }
  if (stage === "failed") {
    return <XCircle size={12} className="text-red-500" />;
  }
  if (stage === "duplicate") {
    return <XCircle size={12} className="text-amber-500" />;
  }
  return <Loader2 size={12} className="animate-spin text-brand-500" />;
}

export function DocumentDropZone() {
  const uploadMutation = useUploadDocument();
  const queryClient = useQueryClient();
  const { activeOrganization } = useOrganizationContext();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadErrors, setUploadErrors] = useState<string[]>([]);
  const [inFlight, setInFlight] = useState<InFlight[]>([]);
  const [uploadedIds, setUploadedIds] = useState<string[]>([]);
  const { data: allDocuments } = useDocuments();

  // Hydrate uploaded ids when org changes
  useEffect(() => {
    if (!activeOrganization) {
      setUploadedIds([]);
      return;
    }
    setUploadedIds(readUploadedIds(activeOrganization.id));
  }, [activeOrganization]);

  const persistIds = useCallback(
    (updater: (prev: string[]) => string[]) => {
      setUploadedIds((prev) => {
        const next = updater(prev);
        if (activeOrganization) {
          writeUploadedIds(activeOrganization.id, next);
        }
        return next;
      });
    },
    [activeOrganization],
  );

  const addUploadedId = useCallback(
    (id: string) => {
      persistIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
    },
    [persistIds],
  );

  const removeUploadedIdInternal = useCallback(
    (id: string) => {
      persistIds((prev) => prev.filter((x) => x !== id));
    },
    [persistIds],
  );

  // Show only docs the user uploaded from this drop zone (tracked by id)
  const myDocs = useMemo(() => {
    if (!allDocuments || uploadedIds.length === 0) return [];
    const idSet = new Set(uploadedIds);
    return allDocuments
      .filter((d) => idSet.has(d.id))
      .sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      );
  }, [allDocuments, uploadedIds]);

  const visibleInFlight = useMemo(() => {
    if (!allDocuments) return inFlight;
    const docNames = new Set(myDocs.map((d) => d.filename));
    return inFlight.filter(
      (f) => f.failed || f.duplicate || !docNames.has(f.filename),
    );
  }, [inFlight, allDocuments, myDocs]);

  const hasPending = useMemo(() => {
    if (visibleInFlight.some((f) => !f.failed && !f.duplicate)) return true;
    return myDocs.some(
      (d) => d.status === "uploaded" || d.status === "processing",
    );
  }, [visibleInFlight, myDocs]);

  useEffect(() => {
    if (!hasPending || !activeOrganization) return;
    const interval = window.setInterval(() => {
      void queryClient.invalidateQueries({
        queryKey: ["documents", activeOrganization.id],
      });
    }, 3000);
    return () => window.clearInterval(interval);
  }, [hasPending, queryClient, activeOrganization]);

  const handleFiles = useCallback(
    (fileList: FileList) => {
      setUploadErrors([]);
      const { valid, errors } = validateFiles(fileList);
      if (errors.length > 0) {
        setUploadErrors(errors);
      }
      for (const vf of valid) {
        const filename = vf.file.name;
        const key = `${filename}-${Date.now()}-${Math.random()}`;
        setInFlight((prev) => [
          ...prev,
          {
            key,
            filename,
            failed: false,
            duplicate: false,
            errorMessage: null,
          },
        ]);
        uploadMutation.mutate(
          { file: vf.file },
          {
            onSuccess: (doc) => {
              addUploadedId(doc.id);
              setInFlight((prev) => prev.filter((f) => f.key !== key));
            },
            onError: (err) => {
              const { status, message } = extractErrorMessage(err);
              const isDuplicate = status === 409;
              setInFlight((prev) =>
                prev.map((f) =>
                  f.key === key
                    ? {
                        ...f,
                        failed: !isDuplicate,
                        duplicate: isDuplicate,
                        errorMessage: message,
                      }
                    : f,
                ),
              );
            },
          },
        );
      }
    },
    [uploadMutation, addUploadedId],
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

  const dismissFailedInFlight = useCallback((key: string) => {
    setInFlight((prev) => prev.filter((f) => f.key !== key));
  }, []);

  const removeUploadedId = removeUploadedIdInternal;

  const totalCount = visibleInFlight.length + myDocs.length;

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

      {totalCount > 0 && (
        <div className="flex flex-col rounded-lg border border-gray-200 bg-white">
          <div className="flex items-center justify-between border-b border-gray-100 px-2 py-1.5">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">
              Uploaded Files ({totalCount})
            </span>
            <div className="flex items-center gap-2 text-[9px] text-gray-400">
              <span title="Upload">U</span>
              <span title="Index">I</span>
            </div>
          </div>
          <ul className="flex max-h-[180px] flex-col gap-0.5 overflow-y-auto px-1.5 py-1.5">
            {visibleInFlight.map((f) => {
              const stage: Stage = f.duplicate
                ? "duplicate"
                : f.failed
                  ? "failed"
                  : "in-progress";
              const dismissable = f.failed || f.duplicate;
              return (
                <FileRow
                  key={f.key}
                  filename={f.filename}
                  uploadStage={stage}
                  indexStage={stage === "duplicate" ? "duplicate" : "in-progress"}
                  errorMessage={f.errorMessage}
                  onDismiss={dismissable ? () => dismissFailedInFlight(f.key) : null}
                />
              );
            })}
            {myDocs.map((doc: DocumentItem) => (
              <FileRow
                key={doc.id}
                filename={doc.filename}
                uploadStage="success"
                indexStage={indexStageFor(doc.status)}
                errorMessage={null}
                onDismiss={() => removeUploadedId(doc.id)}
              />
            ))}
          </ul>
        </div>
      )}

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
        {uploadMutation.isPending ? (
          <Loader2 size={18} className="animate-spin text-brand-500" />
        ) : (
          <Upload
            size={18}
            className={clsx(isDragOver ? "text-brand-500" : "text-gray-400")}
          />
        )}
        <span className="text-[11px] font-medium text-gray-500">
          {uploadMutation.isPending
            ? "Uploading..."
            : isDragOver
              ? "Drop files here"
              : "Drop files or click to upload"}
        </span>
        <span className="text-[10px] text-gray-400">PDF, DOCX, TXT (max {MAX_FILE_SIZE_LABEL})</span>
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

interface FileRowProps {
  filename: string;
  uploadStage: Stage;
  indexStage: Stage;
  errorMessage: string | null;
  onDismiss: (() => void) | null;
}

function uploadTitle(stage: Stage, errorMessage: string | null): string {
  if (stage === "success") return "Uploaded";
  if (stage === "duplicate") return errorMessage ?? "Duplicate file — already indexed";
  if (stage === "failed") return errorMessage ?? "Upload failed";
  return "Uploading";
}

function indexTitle(stage: Stage): string {
  if (stage === "success") return "Indexed";
  if (stage === "duplicate") return "Skipped — duplicate";
  if (stage === "failed") return "Indexing failed";
  return "Indexing";
}

function FileRow({
  filename,
  uploadStage,
  indexStage,
  errorMessage,
  onDismiss,
}: FileRowProps) {
  const isDuplicate = uploadStage === "duplicate";
  return (
    <li
      className={clsx(
        "flex flex-col rounded-md px-1.5 py-1 hover:bg-gray-50",
        isDuplicate && "bg-amber-50",
      )}
      title={filename}
    >
      <div className="flex items-center gap-2">
        <FileText size={12} className="shrink-0 text-gray-400" />
        <span className="flex-1 truncate text-[11px] text-gray-700">{filename}</span>
        <span title={uploadTitle(uploadStage, errorMessage)}>
          <StageIcon stage={uploadStage} />
        </span>
        <span title={indexTitle(indexStage)}>
          <StageIcon stage={indexStage} />
        </span>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="text-[9px] text-gray-400 hover:text-gray-600"
            aria-label="Dismiss"
          >
            ×
          </button>
        )}
      </div>
      {isDuplicate && errorMessage && (
        <p className="ml-5 mt-0.5 text-[10px] text-amber-700">{errorMessage}</p>
      )}
    </li>
  );
}
