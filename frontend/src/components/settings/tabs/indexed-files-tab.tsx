import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileText,
  Loader2,
  RefreshCw,
  Search,
  Trash2,
  Upload,
} from "lucide-react";

import {
  type CrawlSharePointParams,
  type SharePointCrawlResult,
  crawlSharePoint,
  deleteDocument,
  getDocuments,
  getSharePointDrives,
  uploadDocument,
} from "@/api/documents";
import type { DocumentItem, DocumentStatus, SourceType } from "@/types/api";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const SOURCE_TYPE_LABELS: Record<SourceType, { label: string; className: string }> = {
  client: { label: "Client", className: "text-brand-600 bg-brand-50" },
  faa: { label: "FAA", className: "text-brand-800 bg-brand-50" },
  icao: { label: "ICAO", className: "text-accent-700 bg-accent-50" },
  easa: { label: "EASA", className: "text-accent-600 bg-accent-50" },
  nasa_asrs: { label: "NASA ASRS", className: "text-brand-500 bg-brand-50" },
  internal: { label: "Internal", className: "text-gray-600 bg-gray-50" },
};

const STATUS_CONFIG: Record<
  DocumentStatus,
  { icon: typeof CheckCircle2; label: string; className: string }
> = {
  indexed: {
    icon: CheckCircle2,
    label: "Indexed",
    className: "text-brand-500 bg-brand-50",
  },
  processing: {
    icon: Loader2,
    label: "Processing",
    className: "text-accent-500 bg-accent-50",
  },
  uploaded: {
    icon: Clock,
    label: "Uploaded",
    className: "text-brand-400 bg-brand-50",
  },
  failed: {
    icon: AlertTriangle,
    label: "Failed",
    className: "text-red-500 bg-red-50",
  },
};

export function IndexedFilesTab() {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [selectedSourceType, setSelectedSourceType] = useState<SourceType>("client");
  const [crawlResult, setCrawlResult] = useState<SharePointCrawlResult | null>(null);

  const { data: files = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: getDocuments,
    refetchInterval: 10_000,
    retry: false,
  });

  const { data: drives = [] } = useQuery({
    queryKey: ["sharepoint-drives"],
    queryFn: getSharePointDrives,
    retry: false,
    staleTime: 60_000,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
      setDeleteConfirm(null);
    },
  });

  const uploadMutation = useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  const crawlMutation = useMutation({
    mutationFn: crawlSharePoint,
    onSuccess: (result) => {
      setCrawlResult(result);
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  function handleFileUpload() {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".pdf,.docx,.doc,.txt";
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file) {
        uploadMutation.mutate({ file, sourceType: selectedSourceType });
      }
    };
    input.click();
  }

  function handleSharePointSync() {
    setCrawlResult(null);
    const params: CrawlSharePointParams = {
      sourceType: selectedSourceType,
    };
    crawlMutation.mutate(params);
  }

  const filteredFiles = files.filter((file: DocumentItem) =>
    file.filename.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const indexedCount = files.filter(
    (f: DocumentItem) => f.status === "indexed",
  ).length;
  const totalSize = files.reduce(
    (sum: number, f: DocumentItem) => sum + f.size_bytes,
    0,
  );

  function handleDelete(id: string) {
    if (deleteConfirm === id) {
      deleteMutation.mutate(id);
    } else {
      setDeleteConfirm(id);
      setTimeout(() => setDeleteConfirm(null), 3000);
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={24} className="animate-spin text-brand-500" />
      </div>
    );
  }


  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-slate-900">Indexed Files</h2>
        <p className="text-sm text-slate-500">
          Manage documents in your RAG search index.
        </p>
      </div>

      {/* Stats */}
      <div className="mb-6 grid grid-cols-3 gap-4">
        <div className="rounded-2xl border border-gray-200 bg-white p-4">
          <div className="text-2xl font-bold text-brand-600">{indexedCount}</div>
          <div className="text-[12px] text-slate-500">Indexed Documents</div>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4">
          <div className="text-2xl font-bold text-brand-600">{files.length}</div>
          <div className="text-[12px] text-slate-500">Total Documents</div>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4">
          <div className="text-2xl font-bold text-brand-600">
            {formatBytes(totalSize)}
          </div>
          <div className="text-[12px] text-slate-500">Total Size</div>
        </div>
      </div>

      {/* Source Type + Actions */}
      <div className="mb-4 flex items-center gap-3">
        <select
          value={selectedSourceType}
          onChange={(e) => setSelectedSourceType(e.target.value as SourceType)}
          className="rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
        >
          {(Object.entries(SOURCE_TYPE_LABELS) as [SourceType, { label: string }][]).map(
            ([value, { label }]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ),
          )}
        </select>
        <button
          onClick={handleFileUpload}
          disabled={uploadMutation.isPending}
          className="flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-brand-500/20 transition-all hover:bg-brand-600 hover:shadow-lg hover:shadow-brand-500/30 disabled:opacity-50"
        >
          {uploadMutation.isPending ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Upload size={16} />
          )}
          Upload File
        </button>
        <button
          onClick={handleSharePointSync}
          disabled={crawlMutation.isPending}
          className="flex items-center gap-2 rounded-xl border border-brand-200 bg-white px-4 py-2.5 text-sm font-semibold text-brand-700 transition-all hover:bg-brand-50 disabled:opacity-50"
        >
          {crawlMutation.isPending ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <RefreshCw size={16} />
          )}
          Sync from SharePoint
        </button>
        <div className="relative flex-1">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
          />
          <input
            type="text"
            placeholder="Search files..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-xl border border-gray-200 py-2.5 pl-10 pr-4 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
        </div>
      </div>

      {/* Crawl result banner */}
      {crawlResult && (
        <div className="mb-4 rounded-xl border border-brand-200 bg-brand-50 px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="text-sm text-brand-800">
              <span className="font-semibold">SharePoint sync complete:</span>{" "}
              {crawlResult.files_discovered} files found, {crawlResult.files_queued} queued
              for processing
              {crawlResult.skipped_files.length > 0 && (
                <span className="text-brand-600">
                  {" "}({crawlResult.skipped_files.length} already imported)
                </span>
              )}
            </div>
            <button
              onClick={() => setCrawlResult(null)}
              className="text-brand-400 hover:text-brand-600"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Crawl error banner */}
      {crawlMutation.isError && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
          <div className="text-sm text-red-700">
            <span className="font-semibold">SharePoint sync failed:</span>{" "}
            {crawlMutation.error instanceof Error
              ? crawlMutation.error.message
              : "Check that SharePoint credentials are configured on the server."}
          </div>
        </div>
      )}

      {/* SharePoint drives info */}
      {drives.length > 0 && (
        <div className="mb-4 flex items-center gap-2 text-[12px] text-slate-400">
          <span>SharePoint libraries:</span>
          {drives.map((d) => (
            <span key={d.id} className="rounded-full bg-gray-100 px-2 py-0.5 text-slate-600">
              {d.name}
            </span>
          ))}
        </div>
      )}

      {/* File list */}
      <div className="rounded-2xl border border-gray-200 bg-white">
        {filteredFiles.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-400">
            {files.length === 0
              ? "No documents uploaded yet. Upload a file or sync from SharePoint to get started."
              : "No files found matching your search."}
          </div>
        ) : (
          filteredFiles.map((file: DocumentItem, index: number) => {
            const statusConfig = STATUS_CONFIG[file.status];
            const StatusIcon = statusConfig.icon;
            return (
              <div
                key={file.id}
                className={`flex items-center gap-4 px-5 py-4 ${
                  index < filteredFiles.length - 1
                    ? "border-b border-gray-100"
                    : ""
                }`}
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50">
                  <FileText size={18} className="text-brand-500" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-semibold text-slate-800">
                      {file.filename}
                    </span>
                    <span
                      className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${statusConfig.className}`}
                    >
                      <StatusIcon
                        size={10}
                        className={
                          file.status === "processing" ? "animate-spin" : ""
                        }
                      />
                      {statusConfig.label}
                    </span>
                    {file.source_type && (
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${SOURCE_TYPE_LABELS[file.source_type]?.className ?? "text-gray-600 bg-gray-50"}`}
                      >
                        {SOURCE_TYPE_LABELS[file.source_type]?.label ?? file.source_type}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-[12px] text-slate-400">
                    <span>{formatBytes(file.size_bytes)}</span>
                    <span>{file.content_type}</span>
                    <span className="flex items-center gap-1">
                      <Clock size={10} />
                      {formatDate(file.created_at)}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(file.id)}
                  disabled={deleteMutation.isPending}
                  className={`rounded-lg p-2 transition-colors ${
                    deleteConfirm === file.id
                      ? "bg-red-50 text-red-500 hover:bg-red-100"
                      : "text-gray-300 hover:bg-red-50 hover:text-red-500"
                  }`}
                  title={
                    deleteConfirm === file.id
                      ? "Click again to confirm delete"
                      : "Delete from index"
                  }
                >
                  <Trash2 size={16} />
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
