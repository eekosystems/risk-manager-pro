import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  CloudDownload,
  FileText,
  Folder,
  FolderOpen,
  Loader2,
  RefreshCw,
  Search,
  Trash2,
  Upload,
} from "lucide-react";

import {
  type CrawlSharePointParams,
  type SharePointCrawlResult,
  type SyncFolderResult,
  crawlSharePoint,
  deleteDocument,
  getDocuments,
  getSharePointDrives,
  processAllDocuments,
  reindexDocument,
  syncFolder,
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

// --- Tree helpers ---

interface FolderNode {
  name: string;
  path: string;
  files: DocumentItem[];
  children: Map<string, FolderNode>;
}

function buildTree(files: DocumentItem[]): FolderNode {
  const root: FolderNode = { name: "", path: "", files: [], children: new Map() };

  for (const file of files) {
    const folderPath = file.folder_path ?? "";
    if (!folderPath || folderPath === "/") {
      root.files.push(file);
      continue;
    }

    const parts = folderPath.replace(/^\/+|\/+$/g, "").split("/");
    let current = root;
    let builtPath = "";

    for (const part of parts) {
      builtPath = builtPath ? `${builtPath}/${part}` : part;
      if (!current.children.has(part)) {
        current.children.set(part, {
          name: part,
          path: builtPath,
          files: [],
          children: new Map(),
        });
      }
      current = current.children.get(part)!;
    }
    current.files.push(file);
  }

  return root;
}

function countFilesInNode(node: FolderNode): number {
  let count = node.files.length;
  for (const child of node.children.values()) {
    count += countFilesInNode(child);
  }
  return count;
}

// --- File row component ---

function FileRow({
  file,
  depth,
  deleteConfirm,
  onDelete,
  onReindex,
  isDeleting,
  isReindexing,
  isLast,
}: {
  file: DocumentItem;
  depth: number;
  deleteConfirm: string | null;
  onDelete: (id: string) => void;
  onReindex: (id: string) => void;
  isDeleting: boolean;
  isReindexing: boolean;
  isLast: boolean;
}) {
  const statusConfig = STATUS_CONFIG[file.status];
  const StatusIcon = statusConfig.icon;
  const isFailed = file.status === "failed";
  const isProcessing = file.status === "processing";

  return (
    <div
      className={`flex items-center gap-3 px-5 py-3 ${!isLast ? "border-b border-gray-100" : ""}`}
      style={{ paddingLeft: `${20 + depth * 24}px` }}
    >
      <FileText size={16} className="shrink-0 text-brand-400" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-slate-800">
            {file.filename}
          </span>
          <span
            className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${statusConfig.className}`}
          >
            <StatusIcon
              size={10}
              className={isProcessing ? "animate-spin" : ""}
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
        <div className="flex items-center gap-3 text-[11px] text-slate-400">
          <span>{formatBytes(file.size_bytes)}</span>
          <span>{file.content_type}</span>
          <span className="flex items-center gap-1">
            <Clock size={9} />
            {formatDate(file.created_at)}
          </span>
        </div>
      </div>
      <button
        onClick={() => onReindex(file.id)}
        disabled={isReindexing || isProcessing}
        className={`shrink-0 rounded-lg p-1.5 transition-colors ${
          isFailed
            ? "text-red-400 hover:bg-accent-50 hover:text-accent-600"
            : "text-gray-300 hover:bg-brand-50 hover:text-brand-500"
        } disabled:opacity-30`}
        title={isFailed ? "Retry" : "Reindex"}
      >
        <RefreshCw size={13} className={isReindexing ? "animate-spin" : ""} />
      </button>
      <button
        onClick={() => onDelete(file.id)}
        disabled={isDeleting}
        className={`shrink-0 rounded-lg p-1.5 transition-colors ${
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
        <Trash2 size={13} />
      </button>
    </div>
  );
}

// --- Folder row component ---

function collectFileIds(node: FolderNode): string[] {
  const ids = node.files.map((f) => f.id);
  for (const child of node.children.values()) {
    ids.push(...collectFileIds(child));
  }
  return ids;
}

function FolderRow({
  node,
  depth,
  expanded,
  onToggle,
  deleteConfirm,
  onDelete,
  onReindex,
  onReindexMany,
  onSyncFolder,
  syncingFolder,
  isDeleting,
  isReindexing,
}: {
  node: FolderNode;
  depth: number;
  expanded: Set<string>;
  onToggle: (path: string) => void;
  deleteConfirm: string | null;
  onDelete: (id: string) => void;
  onReindex: (id: string) => void;
  onReindexMany: (ids: string[]) => void;
  onSyncFolder: (path: string) => void;
  syncingFolder: string | null;
  isDeleting: boolean;
  isReindexing: boolean;
}) {
  const isOpen = expanded.has(node.path);
  const fileCount = countFilesInNode(node);
  const FolderIcon = isOpen ? FolderOpen : Folder;
  const ChevronIcon = isOpen ? ChevronDown : ChevronRight;

  const sortedChildren = [...node.children.values()].sort((a, b) =>
    a.name.localeCompare(b.name),
  );

  return (
    <>
      <div className="flex items-center border-b border-gray-100">
        <button
          onClick={() => onToggle(node.path)}
          className="flex flex-1 items-center gap-2 px-5 py-2.5 text-left transition-colors hover:bg-gray-50"
          style={{ paddingLeft: `${12 + depth * 24}px` }}
        >
          <ChevronIcon size={14} className="shrink-0 text-slate-400" />
          <FolderIcon size={16} className="shrink-0 text-accent-500" />
          <span className="text-sm font-semibold text-slate-700">{node.name}</span>
          <span className="text-[11px] text-slate-400">({fileCount})</span>
        </button>
        {(() => {
          const isSyncingThis = syncingFolder === node.path;
          const isSyncingAny = syncingFolder !== null;
          return (
            <button
              onClick={() => onSyncFolder(node.path)}
              disabled={isSyncingAny}
              className={`shrink-0 rounded-lg p-1.5 transition-colors ${
                isSyncingThis
                  ? "bg-accent-50 text-accent-600"
                  : "text-gray-300 hover:bg-accent-50 hover:text-accent-600"
              } disabled:opacity-30`}
              title={isSyncingThis ? "Syncing..." : "Re-sync from SharePoint"}
            >
              {isSyncingThis ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <CloudDownload size={13} />
              )}
            </button>
          );
        })()}
        <button
          onClick={() => onReindexMany(collectFileIds(node))}
          disabled={isReindexing}
          className="mr-3 shrink-0 rounded-lg p-1.5 text-gray-300 transition-colors hover:bg-brand-50 hover:text-brand-500 disabled:opacity-30"
          title="Reindex folder"
        >
          <RefreshCw size={13} />
        </button>
      </div>
      {isOpen && (
        <>
          {sortedChildren.map((child) => (
            <FolderRow
              key={child.path}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              onToggle={onToggle}
              deleteConfirm={deleteConfirm}
              onDelete={onDelete}
              onReindex={onReindex}
              onReindexMany={onReindexMany}
              onSyncFolder={onSyncFolder}
              syncingFolder={syncingFolder}
              isDeleting={isDeleting}
              isReindexing={isReindexing}
            />
          ))}
          {node.files.map((file, i) => (
            <FileRow
              key={file.id}
              file={file}
              depth={depth + 1}
              deleteConfirm={deleteConfirm}
              onDelete={onDelete}
              onReindex={onReindex}
              isDeleting={isDeleting}
              isReindexing={isReindexing}
              isLast={i === node.files.length - 1 && sortedChildren.length === 0}
            />
          ))}
        </>
      )}
    </>
  );
}

// --- Main component ---

export function IndexedFilesTab() {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [selectedSourceType, setSelectedSourceType] = useState<SourceType>("client");
  const [crawlResult, setCrawlResult] = useState<SharePointCrawlResult | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

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

  const reindexMutation = useMutation({
    mutationFn: reindexDocument,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  function handleReindex(id: string) {
    reindexMutation.mutate(id);
  }

  function handleReindexMany(ids: string[]) {
    for (const id of ids) {
      reindexMutation.mutate(id);
    }
  }

  const [processAllResult, setProcessAllResult] = useState<{ queued: number } | null>(null);

  const processAllMutation = useMutation({
    mutationFn: processAllDocuments,
    onSuccess: (result) => {
      setProcessAllResult(result);
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  function handleReindexAll() {
    setProcessAllResult(null);
    processAllMutation.mutate();
  }

  const [syncResult, setSyncResult] = useState<SyncFolderResult | null>(null);
  const [syncingFolder, setSyncingFolder] = useState<string | null>(null);

  const syncFolderMutation = useMutation({
    mutationFn: (folderPath: string) => syncFolder(folderPath, selectedSourceType),
    onSuccess: (result) => {
      setSyncResult(result);
      setSyncingFolder(null);
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: () => {
      setSyncingFolder(null);
    },
  });

  function handleSyncFolder(path: string) {
    setSyncResult(null);
    setSyncingFolder(path);
    syncFolderMutation.mutate(path);
  }

  const filteredFiles = useMemo(
    () =>
      searchQuery
        ? files.filter((f: DocumentItem) =>
            f.filename.toLowerCase().includes(searchQuery.toLowerCase()),
          )
        : files,
    [files, searchQuery],
  );

  const tree = useMemo(() => buildTree(filteredFiles), [filteredFiles]);
  const hasTree = tree.children.size > 0;

  const indexedCount = files.filter((f: DocumentItem) => f.status === "indexed").length;
  const totalSize = files.reduce((sum: number, f: DocumentItem) => sum + f.size_bytes, 0);

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
    const params: CrawlSharePointParams = { sourceType: selectedSourceType };
    crawlMutation.mutate(params);
  }

  function handleDelete(id: string) {
    if (deleteConfirm === id) {
      deleteMutation.mutate(id);
    } else {
      setDeleteConfirm(id);
      setTimeout(() => setDeleteConfirm(null), 3000);
    }
  }

  function toggleFolder(path: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }

  function expandAll() {
    const paths = new Set<string>();
    function walk(node: FolderNode) {
      if (node.path) paths.add(node.path);
      for (const child of node.children.values()) walk(child);
    }
    walk(tree);
    setExpanded(paths);
  }

  function collapseAll() {
    setExpanded(new Set());
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={24} className="animate-spin text-brand-500" />
      </div>
    );
  }

  const sortedRootChildren = [...tree.children.values()].sort((a, b) =>
    a.name.localeCompare(b.name),
  );

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
        {files.length > 0 && (
          <button
            onClick={handleReindexAll}
            disabled={processAllMutation.isPending}
            className="flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-600 transition-all hover:bg-gray-50 disabled:opacity-50"
          >
            {processAllMutation.isPending ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <RefreshCw size={16} />
            )}
            Process All
          </button>
        )}
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

      {/* Process all result banner */}
      {processAllResult && (
        <div className="mb-4 rounded-xl border border-brand-200 bg-brand-50 px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="text-sm text-brand-800">
              <span className="font-semibold">Processing queued:</span>{" "}
              {processAllResult.queued} documents will be processed in the background.
              Watch the status update automatically.
            </div>
            <button
              onClick={() => setProcessAllResult(null)}
              className="text-brand-400 hover:text-brand-600"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Folder sync result banner */}
      {syncResult && (
        <div className="mb-4 rounded-xl border border-accent-200 bg-accent-50 px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="text-sm text-accent-800">
              <span className="font-semibold">Folder sync complete ({syncResult.folder_path}):</span>{" "}
              {syncResult.files_found} files found, {syncResult.files_updated} updated,{" "}
              {syncResult.files_new} new
            </div>
            <button
              onClick={() => setSyncResult(null)}
              className="text-accent-400 hover:text-accent-600"
            >
              ✕
            </button>
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

      {/* Expand/Collapse controls */}
      {hasTree && (
        <div className="mb-2 flex items-center gap-2">
          <button
            onClick={expandAll}
            className="text-[12px] font-medium text-brand-600 hover:text-brand-800"
          >
            Expand all
          </button>
          <span className="text-slate-300">|</span>
          <button
            onClick={collapseAll}
            className="text-[12px] font-medium text-brand-600 hover:text-brand-800"
          >
            Collapse all
          </button>
        </div>
      )}

      {/* File tree */}
      <div className="rounded-2xl border border-gray-200 bg-white">
        {filteredFiles.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-400">
            {files.length === 0
              ? "No documents uploaded yet. Upload a file or sync from SharePoint to get started."
              : "No files found matching your search."}
          </div>
        ) : (
          <>
            {/* Folders */}
            {sortedRootChildren.map((child) => (
              <FolderRow
                key={child.path}
                node={child}
                depth={0}
                expanded={expanded}
                onToggle={toggleFolder}
                deleteConfirm={deleteConfirm}
                onDelete={handleDelete}
                onReindex={handleReindex}
                onReindexMany={handleReindexMany}
                onSyncFolder={handleSyncFolder}
                syncingFolder={syncingFolder}
                isDeleting={deleteMutation.isPending}
                isReindexing={reindexMutation.isPending}
              />
            ))}
            {/* Root-level files (no folder) */}
            {tree.files.map((file, i) => (
              <FileRow
                key={file.id}
                file={file}
                depth={0}
                deleteConfirm={deleteConfirm}
                onDelete={handleDelete}
                onReindex={handleReindex}
                isDeleting={deleteMutation.isPending}
                isReindexing={reindexMutation.isPending}
                isLast={i === tree.files.length - 1}
              />
            ))}
          </>
        )}
      </div>
    </div>
  );
}
