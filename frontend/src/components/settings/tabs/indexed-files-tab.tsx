import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileText,
  Loader2,
  Search,
  Trash2,
  Upload,
} from "lucide-react";

type FileStatus = "indexed" | "processing" | "failed";

interface IndexedFile {
  id: string;
  filename: string;
  contentType: string;
  sizeBytes: number;
  status: FileStatus;
  chunkCount: number;
  indexedAt: string;
  category: string;
}

const DEMO_FILES: IndexedFile[] = [
  {
    id: "1",
    filename: "FAA-AC-120-92B-SMS-Advisory.pdf",
    contentType: "application/pdf",
    sizeBytes: 2_450_000,
    status: "indexed",
    chunkCount: 87,
    indexedAt: "2026-03-05T10:30:00Z",
    category: "FAA Regulations",
  },
  {
    id: "2",
    filename: "ICAO-Annex-19-Safety-Management.pdf",
    contentType: "application/pdf",
    sizeBytes: 5_100_000,
    status: "indexed",
    chunkCount: 156,
    indexedAt: "2026-03-04T14:22:00Z",
    category: "ICAO Standards",
  },
  {
    id: "3",
    filename: "Faith-Group-SRA-Template-2026.docx",
    contentType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    sizeBytes: 890_000,
    status: "indexed",
    chunkCount: 34,
    indexedAt: "2026-03-03T09:15:00Z",
    category: "Safety Risk Assessments",
  },
  {
    id: "4",
    filename: "PHL-Operational-Checklist-v3.pdf",
    contentType: "application/pdf",
    sizeBytes: 1_200_000,
    status: "indexed",
    chunkCount: 45,
    indexedAt: "2026-03-02T16:45:00Z",
    category: "Safety Risk Assessments",
  },
  {
    id: "5",
    filename: "FAR-Part-91-Operations.pdf",
    contentType: "application/pdf",
    sizeBytes: 3_800_000,
    status: "indexed",
    chunkCount: 112,
    indexedAt: "2026-03-01T11:00:00Z",
    category: "FAA Regulations",
  },
  {
    id: "6",
    filename: "Risk-Matrix-Best-Practices-Guide.pdf",
    contentType: "application/pdf",
    sizeBytes: 670_000,
    status: "indexed",
    chunkCount: 28,
    indexedAt: "2026-02-28T13:30:00Z",
    category: "Best Practice Guides",
  },
  {
    id: "7",
    filename: "SMS-Implementation-Handbook.pdf",
    contentType: "application/pdf",
    sizeBytes: 4_200_000,
    status: "indexed",
    chunkCount: 134,
    indexedAt: "2026-02-27T09:45:00Z",
    category: "Best Practice Guides",
  },
  {
    id: "8",
    filename: "Quarterly-Safety-Report-Q4-2025.pdf",
    contentType: "application/pdf",
    sizeBytes: 1_800_000,
    status: "processing",
    chunkCount: 0,
    indexedAt: "2026-03-08T22:10:00Z",
    category: "Safety Risk Assessments",
  },
  {
    id: "9",
    filename: "Corrupted-Upload-Test.pdf",
    contentType: "application/pdf",
    sizeBytes: 45_000,
    status: "failed",
    chunkCount: 0,
    indexedAt: "2026-03-07T08:00:00Z",
    category: "Other",
  },
];

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

const STATUS_CONFIG: Record<
  FileStatus,
  { icon: typeof CheckCircle2; label: string; className: string }
> = {
  indexed: {
    icon: CheckCircle2,
    label: "Indexed",
    className: "text-green-500 bg-green-50",
  },
  processing: {
    icon: Loader2,
    label: "Processing",
    className: "text-amber-500 bg-amber-50",
  },
  failed: {
    icon: AlertTriangle,
    label: "Failed",
    className: "text-red-500 bg-red-50",
  },
};

export function IndexedFilesTab() {
  const [files, setFiles] = useState<IndexedFile[]>(DEMO_FILES);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const categories = ["all", ...new Set(DEMO_FILES.map((f) => f.category))];

  const filteredFiles = files.filter((file) => {
    const matchesSearch = file.filename
      .toLowerCase()
      .includes(searchQuery.toLowerCase());
    const matchesCategory =
      filterCategory === "all" || file.category === filterCategory;
    return matchesSearch && matchesCategory;
  });

  const totalChunks = files
    .filter((f) => f.status === "indexed")
    .reduce((sum, f) => sum + f.chunkCount, 0);

  function handleDelete(id: string) {
    if (deleteConfirm === id) {
      setFiles((prev) => prev.filter((f) => f.id !== id));
      setDeleteConfirm(null);
    } else {
      setDeleteConfirm(id);
      setTimeout(() => setDeleteConfirm(null), 3000);
    }
  }

  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-slate-900">Indexed Files</h2>
        <p className="text-sm text-slate-500">
          Manage documents in your RAG search index.
        </p>
      </div>

      {/* Stats */}
      <div className="mb-6 grid grid-cols-3 gap-4">
        <div className="rounded-2xl border border-gray-200 bg-white p-4">
          <div className="text-2xl font-bold text-brand-500">
            {files.filter((f) => f.status === "indexed").length}
          </div>
          <div className="text-[12px] text-slate-500">Indexed Documents</div>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4">
          <div className="text-2xl font-bold text-brand-500">{totalChunks}</div>
          <div className="text-[12px] text-slate-500">Total Chunks</div>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4">
          <div className="text-2xl font-bold text-brand-500">
            {formatBytes(
              files.reduce((sum, f) => sum + f.sizeBytes, 0),
            )}
          </div>
          <div className="text-[12px] text-slate-500">Total Size</div>
        </div>
      </div>

      {/* Upload button + Search bar */}
      <div className="mb-4 flex items-center gap-3">
        <button className="flex items-center gap-2 rounded-xl gradient-brand px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-brand-500/20 transition-all hover:shadow-lg hover:shadow-brand-500/30">
          <Upload size={16} />
          Upload Document
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
        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          className="rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-600 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
        >
          {categories.map((cat) => (
            <option key={cat} value={cat}>
              {cat === "all" ? "All Categories" : cat}
            </option>
          ))}
        </select>
      </div>

      {/* File list */}
      <div className="rounded-2xl border border-gray-200 bg-white">
        {filteredFiles.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-400">
            No files found matching your search.
          </div>
        ) : (
          filteredFiles.map((file, index) => {
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
                <div className="flex-1 min-w-0">
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
                  </div>
                  <div className="flex items-center gap-3 text-[12px] text-slate-400">
                    <span>{formatBytes(file.sizeBytes)}</span>
                    <span>{file.category}</span>
                    {file.chunkCount > 0 && (
                      <span>{file.chunkCount} chunks</span>
                    )}
                    <span className="flex items-center gap-1">
                      <Clock size={10} />
                      {formatDate(file.indexedAt)}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(file.id)}
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
