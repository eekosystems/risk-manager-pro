import { useMemo, useRef, useState } from "react";
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
  FolderPlus,
  GripVertical,
  Loader2,
  Pencil,
  RefreshCw,
  Search,
  Trash2,
} from "lucide-react";

import {
  createDocumentFolder,
  deleteDocumentFolder,
  getDocumentFolders,
  moveDocumentFolder,
  renameDocumentFolder,
} from "@/api/document-folders";
import {
  type CrawlSharePointParams,
  type SharePointCrawlResult,
  type SyncFolderResult,
  crawlSharePoint,
  deleteDocument,
  getDocuments,
  getSharePointDrives,
  moveDocuments,
  processAllDocuments,
  reindexDocument,
  syncFolder,
} from "@/api/documents";
import { formatFileSize } from "@/lib/file-validation";
import type {
  DocumentFolder,
  DocumentItem,
  DocumentStatus,
  SourceType,
} from "@/types/api";

// All SharePoint syncs stamp documents with the "client" source type.
// The user-facing source-type selector was removed because every synced
// document is by definition a client document; non-client sources (FAA,
// ICAO, etc.) are seeded server-side, not chosen at sync time.
const DEFAULT_SOURCE_TYPE: SourceType = "client";

const formatBytes = formatFileSize;

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

// --- Tree model ---

/**
 * A folder in the tree, from one of two sources:
 *
 * - "user"        — a real folder record the user created. Files land here by
 *                   `folder_id`, and it is the only kind that accepts drops.
 * - "sharepoint"  — synthesized from a document's `folder_path`, which mirrors
 *                   the source SharePoint hierarchy. These have no record of
 *                   their own, so they cannot be renamed, moved, or dropped into.
 */
type FolderKind = "user" | "sharepoint";

interface FolderNode {
  kind: FolderKind;
  /** Folder record id — user folders only. */
  id: string | null;
  /** SharePoint path — sharepoint folders only. */
  path: string;
  /** Stable identity for React keys and the expansion set. */
  key: string;
  name: string;
  files: DocumentItem[];
  children: FolderNode[];
}

function userKey(id: string): string {
  return `user:${id}`;
}

function pathKey(path: string): string {
  return `path:${path}`;
}

function makeUserNode(folder: DocumentFolder): FolderNode {
  return {
    kind: "user",
    id: folder.id,
    path: "",
    key: userKey(folder.id),
    name: folder.name,
    files: [],
    children: [],
  };
}

interface Tree {
  /** Top-level folders, user folders first, then the SharePoint mirror. */
  folders: FolderNode[];
  /** Documents filed nowhere: no in-app folder and no SharePoint path. */
  files: DocumentItem[];
}

/**
 * Merge the user's folders with the SharePoint path hierarchy into one tree.
 *
 * A document is placed by `folder_id` when the user has filed it, and falls
 * back to its `folder_path` otherwise — so documents nobody has touched keep
 * rendering exactly where they always did.
 */
function buildTree(files: DocumentItem[], folders: DocumentFolder[]): Tree {
  const userNodes = new Map<string, FolderNode>();
  for (const folder of folders) {
    userNodes.set(folder.id, makeUserNode(folder));
  }

  const rootUserFolders: FolderNode[] = [];
  for (const folder of folders) {
    const node = userNodes.get(folder.id);
    if (!node) continue;
    const parent = folder.parent_id ? userNodes.get(folder.parent_id) : undefined;
    if (parent) {
      parent.children.push(node);
    } else {
      rootUserFolders.push(node);
    }
  }

  // SharePoint mirror folders, keyed by their full path so a repeated path
  // segment resolves to the node that already exists.
  const sharePointNodes = new Map<string, FolderNode>();
  const sharePointRoots: FolderNode[] = [];
  const rootFiles: DocumentItem[] = [];

  for (const file of files) {
    const filed = file.folder_id ? userNodes.get(file.folder_id) : undefined;
    if (filed) {
      filed.files.push(file);
      continue;
    }

    const folderPath = file.folder_path ?? "";
    if (!folderPath || folderPath === "/") {
      rootFiles.push(file);
      continue;
    }

    const parts = folderPath.replace(/^\/+|\/+$/g, "").split("/");
    let parent: FolderNode | null = null;
    let builtPath = "";

    for (const part of parts) {
      builtPath = builtPath ? `${builtPath}/${part}` : part;
      let node = sharePointNodes.get(builtPath);
      if (!node) {
        node = {
          kind: "sharepoint",
          id: null,
          path: builtPath,
          key: pathKey(builtPath),
          name: part,
          files: [],
          children: [],
        };
        sharePointNodes.set(builtPath, node);
        if (parent) {
          parent.children.push(node);
        } else {
          sharePointRoots.push(node);
        }
      }
      parent = node;
    }

    if (parent) parent.files.push(file);
  }

  return {
    folders: [...sortNodes(rootUserFolders), ...sortNodes(sharePointRoots)],
    files: rootFiles,
  };
}

function sortNodes(nodes: FolderNode[]): FolderNode[] {
  const sorted = [...nodes].sort((a, b) => a.name.localeCompare(b.name));
  for (const node of sorted) {
    node.children = [
      ...sortNodes(node.children.filter((c) => c.kind === "user")),
      ...sortNodes(node.children.filter((c) => c.kind === "sharepoint")),
    ];
  }
  return sorted;
}

/**
 * Drop folders that hold no files, so a search shows only what matched.
 * Only applied while searching — an empty folder is meaningful otherwise.
 */
function pruneEmpty(nodes: FolderNode[]): FolderNode[] {
  const kept: FolderNode[] = [];
  for (const node of nodes) {
    const children = pruneEmpty(node.children);
    if (node.files.length === 0 && children.length === 0) continue;
    kept.push({ ...node, children });
  }
  return kept;
}

function countFilesInNode(node: FolderNode): number {
  let count = node.files.length;
  for (const child of node.children) {
    count += countFilesInNode(child);
  }
  return count;
}

function collectFileIds(node: FolderNode): string[] {
  const ids = node.files.map((f) => f.id);
  for (const child of node.children) {
    ids.push(...collectFileIds(child));
  }
  return ids;
}

function collectKeys(nodes: FolderNode[], into: Set<string>): Set<string> {
  for (const node of nodes) {
    into.add(node.key);
    collectKeys(node.children, into);
  }
  return into;
}

/** True when `folderId` is `candidate` or one of its descendants. */
function isSelfOrDescendant(
  folders: DocumentFolder[],
  candidate: string,
  folderId: string,
): boolean {
  if (candidate === folderId) return true;
  const byId = new Map(folders.map((f) => [f.id, f]));
  let current = byId.get(candidate);
  const seen = new Set<string>();
  while (current?.parent_id) {
    if (seen.has(current.parent_id)) break;
    seen.add(current.parent_id);
    if (current.parent_id === folderId) return true;
    current = byId.get(current.parent_id);
  }
  return false;
}

// --- Drag state ---

type DragItem =
  | { kind: "file"; id: string; label: string }
  | { kind: "folder"; id: string; label: string };

// --- Inline folder name editor ---

function FolderNameInput({
  initialValue,
  depth,
  onSubmit,
  onCancel,
  isPending,
}: {
  initialValue: string;
  depth: number;
  onSubmit: (name: string) => void;
  onCancel: () => void;
  isPending: boolean;
}) {
  const [value, setValue] = useState(initialValue);

  return (
    <div
      className="flex items-center gap-2 border-b border-gray-100 bg-brand-50/40 px-5 py-2 last:border-b-0"
      style={{ paddingLeft: `${12 + depth * 24}px` }}
    >
      <Folder size={16} className="shrink-0 text-accent-500" />
      <input
        autoFocus
        type="text"
        value={value}
        disabled={isPending}
        placeholder="Folder name"
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            if (value.trim()) onSubmit(value.trim());
          } else if (e.key === "Escape") {
            e.preventDefault();
            onCancel();
          }
        }}
        onBlur={() => {
          if (!isPending) onCancel();
        }}
        className="flex-1 rounded-lg border border-brand-300 bg-white px-2 py-1 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
      />
      {isPending && <Loader2 size={14} className="animate-spin text-brand-500" />}
    </div>
  );
}

// --- File row ---

function FileRow({
  file,
  depth,
  deleteConfirm,
  onDelete,
  onReindex,
  isDeleting,
  isReindexing,
  onDragStart,
  onDragEnd,
  isDragging,
}: {
  file: DocumentItem;
  depth: number;
  deleteConfirm: string | null;
  onDelete: (id: string) => void;
  onReindex: (id: string) => void;
  isDeleting: boolean;
  isReindexing: boolean;
  onDragStart: (item: DragItem) => void;
  onDragEnd: () => void;
  isDragging: boolean;
}) {
  const statusConfig = STATUS_CONFIG[file.status];
  const StatusIcon = statusConfig.icon;
  const isFailed = file.status === "failed";
  const isProcessing = file.status === "processing";

  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", file.filename);
        onDragStart({ kind: "file", id: file.id, label: file.filename });
      }}
      onDragEnd={onDragEnd}
      className={`group flex items-center gap-3 border-b border-gray-100 px-5 py-3 last:border-b-0 ${
        isDragging ? "opacity-40" : ""
      }`}
      style={{ paddingLeft: `${20 + depth * 24}px` }}
    >
      <GripVertical
        size={14}
        className="shrink-0 cursor-grab text-gray-200 group-hover:text-gray-400"
      />
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

// --- Folder row ---

interface FolderRowProps {
  node: FolderNode;
  depth: number;
  expanded: Set<string>;
  onToggle: (key: string) => void;
  deleteConfirm: string | null;
  onDelete: (id: string) => void;
  onReindex: (id: string) => void;
  onReindexMany: (ids: string[]) => void;
  onSyncFolder: (path: string) => void;
  syncingFolder: string | null;
  isDeleting: boolean;
  isReindexing: boolean;
  // Folder management
  onAddSubfolder: (parentId: string) => void;
  onStartRename: (folderId: string) => void;
  onDeleteFolder: (folderId: string) => void;
  folderDeleteConfirm: string | null;
  renamingId: string | null;
  creatingIn: string | null;
  onSubmitName: (name: string) => void;
  onCancelName: () => void;
  isNamePending: boolean;
  // Drag and drop
  dragItem: DragItem | null;
  dropTargetKey: string | null;
  onDragStart: (item: DragItem) => void;
  onDragEnd: () => void;
  onDragOverFolder: (node: FolderNode) => void;
  onDropOnFolder: (node: FolderNode) => void;
  canDropOn: (node: FolderNode) => boolean;
}

function FolderRow(props: FolderRowProps) {
  const {
    node,
    depth,
    expanded,
    onToggle,
    onSyncFolder,
    syncingFolder,
    onReindexMany,
    isReindexing,
    onAddSubfolder,
    onStartRename,
    onDeleteFolder,
    folderDeleteConfirm,
    renamingId,
    creatingIn,
    onSubmitName,
    onCancelName,
    isNamePending,
    dragItem,
    dropTargetKey,
    onDragStart,
    onDragEnd,
    onDragOverFolder,
    onDropOnFolder,
    canDropOn,
  } = props;

  const isOpen = expanded.has(node.key);
  const fileCount = countFilesInNode(node);
  const FolderIcon = isOpen ? FolderOpen : Folder;
  const ChevronIcon = isOpen ? ChevronDown : ChevronRight;
  const isUserFolder = node.kind === "user";
  const isDropTarget = dropTargetKey === node.key && canDropOn(node);
  const isBeingDragged =
    dragItem?.kind === "folder" && dragItem.id === node.id;

  if (isUserFolder && node.id && renamingId === node.id) {
    return (
      <FolderNameInput
        initialValue={node.name}
        depth={depth}
        onSubmit={onSubmitName}
        onCancel={onCancelName}
        isPending={isNamePending}
      />
    );
  }

  return (
    <>
      <div
        draggable={isUserFolder}
        onDragStart={(e) => {
          if (!isUserFolder || !node.id) return;
          e.stopPropagation();
          e.dataTransfer.effectAllowed = "move";
          e.dataTransfer.setData("text/plain", node.name);
          onDragStart({ kind: "folder", id: node.id, label: node.name });
        }}
        onDragEnd={onDragEnd}
        onDragOver={(e) => {
          if (!dragItem) return;
          e.preventDefault();
          e.stopPropagation();
          if (canDropOn(node)) {
            e.dataTransfer.dropEffect = "move";
            onDragOverFolder(node);
          } else {
            // A SharePoint mirror folder is not a real destination. Refuse the
            // drop here rather than letting it fall through to the top level.
            e.dataTransfer.dropEffect = "none";
            onDragOverFolder(node);
          }
        }}
        onDrop={(e) => {
          if (!dragItem) return;
          e.preventDefault();
          e.stopPropagation();
          if (canDropOn(node)) onDropOnFolder(node);
          else onDragEnd();
        }}
        className={`flex items-center border-b border-gray-100 last:border-b-0 ${
          isDropTarget ? "bg-brand-50 ring-2 ring-inset ring-brand-400" : ""
        } ${isBeingDragged ? "opacity-40" : ""}`}
      >
        <button
          onClick={() => onToggle(node.key)}
          className="flex flex-1 items-center gap-2 px-5 py-2.5 text-left transition-colors hover:bg-gray-50"
          style={{ paddingLeft: `${12 + depth * 24}px` }}
        >
          <ChevronIcon size={14} className="shrink-0 text-slate-400" />
          <FolderIcon
            size={16}
            className={`shrink-0 ${isUserFolder ? "text-brand-500" : "text-accent-500"}`}
          />
          <span className="text-sm font-semibold text-slate-700">{node.name}</span>
          <span className="text-[11px] text-slate-400">({fileCount})</span>
        </button>

        {isUserFolder && node.id ? (
          <>
            <button
              onClick={() => onAddSubfolder(node.id as string)}
              className="shrink-0 rounded-lg p-1.5 text-gray-300 transition-colors hover:bg-brand-50 hover:text-brand-500"
              title="New subfolder"
            >
              <FolderPlus size={13} />
            </button>
            <button
              onClick={() => onStartRename(node.id as string)}
              className="shrink-0 rounded-lg p-1.5 text-gray-300 transition-colors hover:bg-brand-50 hover:text-brand-500"
              title="Rename folder"
            >
              <Pencil size={13} />
            </button>
          </>
        ) : (
          (() => {
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
          })()
        )}

        <button
          onClick={() => onReindexMany(collectFileIds(node))}
          disabled={isReindexing}
          className="shrink-0 rounded-lg p-1.5 text-gray-300 transition-colors hover:bg-brand-50 hover:text-brand-500 disabled:opacity-30"
          title="Reindex folder"
        >
          <RefreshCw size={13} />
        </button>

        {isUserFolder && node.id ? (
          <button
            onClick={() => onDeleteFolder(node.id as string)}
            className={`mr-3 shrink-0 rounded-lg p-1.5 transition-colors ${
              folderDeleteConfirm === node.id
                ? "bg-red-50 text-red-500 hover:bg-red-100"
                : "text-gray-300 hover:bg-red-50 hover:text-red-500"
            }`}
            title={
              folderDeleteConfirm === node.id
                ? "Click again to confirm — files inside move back to the top level"
                : "Delete folder"
            }
          >
            <Trash2 size={13} />
          </button>
        ) : (
          <span className="mr-3" />
        )}
      </div>

      {isOpen && (
        <>
          {isUserFolder && node.id && creatingIn === node.id && (
            <FolderNameInput
              initialValue=""
              depth={depth + 1}
              onSubmit={onSubmitName}
              onCancel={onCancelName}
              isPending={isNamePending}
            />
          )}
          {node.children.map((child) => (
            <FolderRow key={child.key} {...props} node={child} depth={depth + 1} />
          ))}
          {node.files.map((file) => (
            <FileRow
              key={file.id}
              file={file}
              depth={depth + 1}
              deleteConfirm={props.deleteConfirm}
              onDelete={props.onDelete}
              onReindex={props.onReindex}
              isDeleting={props.isDeleting}
              isReindexing={props.isReindexing}
              onDragStart={onDragStart}
              onDragEnd={onDragEnd}
              isDragging={dragItem?.kind === "file" && dragItem.id === file.id}
            />
          ))}
          {isUserFolder && node.files.length === 0 && node.children.length === 0 && (
            <div
              className="border-b border-gray-100 py-3 text-[12px] italic text-slate-300 last:border-b-0"
              style={{ paddingLeft: `${44 + depth * 24}px` }}
            >
              Empty — drag files here
            </div>
          )}
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
  const [crawlResult, setCrawlResult] = useState<SharePointCrawlResult | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // Folder management state
  const [creatingIn, setCreatingIn] = useState<string | null>(null);
  const [creatingAtRoot, setCreatingAtRoot] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [folderDeleteConfirm, setFolderDeleteConfirm] = useState<string | null>(null);
  const [folderError, setFolderError] = useState<string | null>(null);

  // Drag and drop state
  const [dragItem, setDragItem] = useState<DragItem | null>(null);
  const [dropTargetKey, setDropTargetKey] = useState<string | null>(null);
  const [isRootDropTarget, setIsRootDropTarget] = useState(false);
  const autoExpandTimer = useRef<number | null>(null);

  const { data: files = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: getDocuments,
    refetchInterval: 10_000,
    retry: false,
  });

  const { data: folders = [] } = useQuery({
    queryKey: ["document-folders"],
    queryFn: getDocumentFolders,
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
    mutationFn: (folderPath: string) => syncFolder(folderPath, DEFAULT_SOURCE_TYPE),
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

  // --- Folder mutations ---

  function readError(error: unknown, fallback: string): string {
    const detail = (
      error as { response?: { data?: { error?: { message?: string } } } }
    )?.response?.data?.error?.message;
    return detail ?? fallback;
  }

  const createFolderMutation = useMutation({
    mutationFn: createDocumentFolder,
    onSuccess: (folder) => {
      setFolderError(null);
      setCreatingIn(null);
      setCreatingAtRoot(false);
      // Reveal the new folder so it is obvious where it landed.
      setExpanded((prev) => {
        const next = new Set(prev);
        next.add(userKey(folder.id));
        if (folder.parent_id) next.add(userKey(folder.parent_id));
        return next;
      });
      void queryClient.invalidateQueries({ queryKey: ["document-folders"] });
    },
    onError: (error) => {
      setFolderError(readError(error, "Could not create the folder."));
    },
  });

  const renameFolderMutation = useMutation({
    mutationFn: renameDocumentFolder,
    onSuccess: () => {
      setFolderError(null);
      setRenamingId(null);
      void queryClient.invalidateQueries({ queryKey: ["document-folders"] });
    },
    onError: (error) => {
      setFolderError(readError(error, "Could not rename the folder."));
    },
  });

  const deleteFolderMutation = useMutation({
    mutationFn: deleteDocumentFolder,
    onSuccess: () => {
      setFolderError(null);
      setFolderDeleteConfirm(null);
      void queryClient.invalidateQueries({ queryKey: ["document-folders"] });
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (error) => {
      setFolderError(readError(error, "Could not delete the folder."));
    },
  });

  const moveFolderMutation = useMutation({
    mutationFn: moveDocumentFolder,
    onSuccess: () => {
      setFolderError(null);
      void queryClient.invalidateQueries({ queryKey: ["document-folders"] });
    },
    onError: (error) => {
      setFolderError(readError(error, "Could not move the folder."));
    },
  });

  const moveDocumentsMutation = useMutation({
    mutationFn: moveDocuments,
    // Move the row straight away — the request is a single column write, so
    // waiting on the round trip makes the drag feel broken.
    onMutate: async (params) => {
      await queryClient.cancelQueries({ queryKey: ["documents"] });
      const previous = queryClient.getQueryData<DocumentItem[]>(["documents"]);
      queryClient.setQueryData<DocumentItem[]>(["documents"], (current) =>
        (current ?? []).map((doc) =>
          params.documentIds.includes(doc.id)
            ? { ...doc, folder_id: params.folderId }
            : doc,
        ),
      );
      return { previous };
    },
    onError: (error, _params, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["documents"], context.previous);
      }
      setFolderError(readError(error, "Could not move the file."));
    },
    onSuccess: () => {
      setFolderError(null);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  // --- Tree ---

  const filteredFiles = useMemo(
    () =>
      searchQuery
        ? files.filter((f: DocumentItem) =>
            f.filename.toLowerCase().includes(searchQuery.toLowerCase()),
          )
        : files,
    [files, searchQuery],
  );

  const tree = useMemo(() => {
    const built = buildTree(filteredFiles, folders);
    return searchQuery ? { ...built, folders: pruneEmpty(built.folders) } : built;
  }, [filteredFiles, folders, searchQuery]);

  const hasTree = tree.folders.length > 0;

  const indexedCount = files.filter((f: DocumentItem) => f.status === "indexed").length;
  const totalSize = files.reduce((sum: number, f: DocumentItem) => sum + f.size_bytes, 0);

  function handleSharePointSync() {
    setCrawlResult(null);
    const params: CrawlSharePointParams = { sourceType: DEFAULT_SOURCE_TYPE };
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

  function handleDeleteFolder(folderId: string) {
    if (folderDeleteConfirm === folderId) {
      deleteFolderMutation.mutate(folderId);
    } else {
      setFolderDeleteConfirm(folderId);
      setTimeout(() => setFolderDeleteConfirm(null), 3000);
    }
  }

  function toggleFolder(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function expandAll() {
    setExpanded(collectKeys(tree.folders, new Set<string>()));
  }

  function collapseAll() {
    setExpanded(new Set());
  }

  // --- Folder naming ---

  function startCreateAtRoot() {
    setFolderError(null);
    setRenamingId(null);
    setCreatingIn(null);
    setCreatingAtRoot(true);
  }

  function startCreateSubfolder(parentId: string) {
    setFolderError(null);
    setRenamingId(null);
    setCreatingAtRoot(false);
    setCreatingIn(parentId);
    setExpanded((prev) => new Set(prev).add(userKey(parentId)));
  }

  function startRename(folderId: string) {
    setFolderError(null);
    setCreatingIn(null);
    setCreatingAtRoot(false);
    setRenamingId(folderId);
  }

  function cancelNaming() {
    setCreatingIn(null);
    setCreatingAtRoot(false);
    setRenamingId(null);
  }

  function submitName(name: string) {
    if (renamingId) {
      renameFolderMutation.mutate({ folderId: renamingId, name });
    } else if (creatingIn) {
      createFolderMutation.mutate({ name, parentId: creatingIn });
    } else if (creatingAtRoot) {
      createFolderMutation.mutate({ name, parentId: null });
    }
  }

  const isNamePending =
    createFolderMutation.isPending || renameFolderMutation.isPending;

  // --- Drag and drop ---

  function canDropOn(node: FolderNode): boolean {
    // Only real folders hold documents. A SharePoint mirror folder has no
    // record to point `folder_id` at, so it never accepts a drop.
    if (node.kind !== "user" || !node.id || !dragItem) return false;
    if (dragItem.kind === "folder") {
      return !isSelfOrDescendant(folders, node.id, dragItem.id);
    }
    return true;
  }

  function clearAutoExpand() {
    if (autoExpandTimer.current !== null) {
      window.clearTimeout(autoExpandTimer.current);
      autoExpandTimer.current = null;
    }
  }

  function handleDragStart(item: DragItem) {
    setDragItem(item);
    setFolderError(null);
  }

  function handleDragEnd() {
    setDragItem(null);
    setDropTargetKey(null);
    setIsRootDropTarget(false);
    clearAutoExpand();
  }

  function handleDragOverFolder(node: FolderNode) {
    setIsRootDropTarget(false);
    if (dropTargetKey === node.key) return;
    setDropTargetKey(node.key);
    clearAutoExpand();
    if (!expanded.has(node.key)) {
      // Hovering over a closed folder opens it so you can drop deeper in.
      autoExpandTimer.current = window.setTimeout(() => {
        setExpanded((prev) => new Set(prev).add(node.key));
      }, 600);
    }
  }

  function handleDropOnFolder(node: FolderNode) {
    const item = dragItem;
    handleDragEnd();
    if (!item || node.kind !== "user" || !node.id) return;
    if (item.kind === "file") {
      moveDocumentsMutation.mutate({ documentIds: [item.id], folderId: node.id });
    } else if (item.id !== node.id) {
      moveFolderMutation.mutate({ folderId: item.id, parentId: node.id });
    }
  }

  function handleDropOnRoot() {
    const item = dragItem;
    handleDragEnd();
    if (!item) return;
    if (item.kind === "file") {
      moveDocumentsMutation.mutate({ documentIds: [item.id], folderId: null });
    } else {
      moveFolderMutation.mutate({ folderId: item.id, parentId: null });
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={24} className="animate-spin text-brand-500" />
      </div>
    );
  }

  const folderRowProps = {
    expanded,
    onToggle: toggleFolder,
    deleteConfirm,
    onDelete: handleDelete,
    onReindex: handleReindex,
    onReindexMany: handleReindexMany,
    onSyncFolder: handleSyncFolder,
    syncingFolder,
    isDeleting: deleteMutation.isPending,
    isReindexing: reindexMutation.isPending,
    onAddSubfolder: startCreateSubfolder,
    onStartRename: startRename,
    onDeleteFolder: handleDeleteFolder,
    folderDeleteConfirm,
    renamingId,
    creatingIn,
    onSubmitName: submitName,
    onCancelName: cancelNaming,
    isNamePending,
    dragItem,
    dropTargetKey,
    onDragStart: handleDragStart,
    onDragEnd: handleDragEnd,
    onDragOverFolder: handleDragOverFolder,
    onDropOnFolder: handleDropOnFolder,
    canDropOn,
  };

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

      {/* Actions */}
      <div className="mb-4 flex items-center gap-3">
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

      {/* Folder error banner */}
      {folderError && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="text-sm text-red-700">{folderError}</div>
            <button
              onClick={() => setFolderError(null)}
              className="text-red-400 hover:text-red-600"
            >
              ✕
            </button>
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

      {/* Tree controls */}
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {hasTree && (
            <>
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
            </>
          )}
        </div>
        <button
          onClick={startCreateAtRoot}
          className="flex items-center gap-1.5 rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-[12px] font-semibold text-brand-700 transition-colors hover:bg-brand-50"
        >
          <FolderPlus size={14} />
          New Folder
        </button>
      </div>

      {/* File tree */}
      <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white">
        {dragItem && (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              e.stopPropagation();
              e.dataTransfer.dropEffect = "move";
              setDropTargetKey(null);
              setIsRootDropTarget(true);
            }}
            onDragLeave={() => setIsRootDropTarget(false)}
            onDrop={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleDropOnRoot();
            }}
            className={`border-b border-dashed px-5 py-3 text-center text-[12px] font-medium transition-colors ${
              isRootDropTarget
                ? "border-brand-400 bg-brand-50 text-brand-700"
                : "border-gray-300 text-slate-400"
            }`}
          >
            Drop here to move {dragItem.label} to the top level
          </div>
        )}

        {creatingAtRoot && (
          <FolderNameInput
            initialValue=""
            depth={0}
            onSubmit={submitName}
            onCancel={cancelNaming}
            isPending={isNamePending}
          />
        )}

        {filteredFiles.length === 0 && tree.folders.length === 0 && !creatingAtRoot ? (
          <div className="p-8 text-center text-sm text-slate-400">
            {files.length === 0
              ? "No documents indexed yet. Click Sync from SharePoint to get started."
              : "No files found matching your search."}
          </div>
        ) : (
          <>
            {tree.folders.map((node) => (
              <FolderRow key={node.key} {...folderRowProps} node={node} depth={0} />
            ))}
            {tree.files.map((file) => (
              <FileRow
                key={file.id}
                file={file}
                depth={0}
                deleteConfirm={deleteConfirm}
                onDelete={handleDelete}
                onReindex={handleReindex}
                isDeleting={deleteMutation.isPending}
                isReindexing={reindexMutation.isPending}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
                isDragging={dragItem?.kind === "file" && dragItem.id === file.id}
              />
            ))}
          </>
        )}
      </div>

      {tree.folders.some((n) => n.kind === "user") && (
        <p className="mt-2 text-[11px] text-slate-400">
          Drag files onto a folder to file them, or onto the empty space around the
          list to move them back to the top level. Folders are shared with your
          organization and never change anything in SharePoint.
        </p>
      )}
    </div>
  );
}
