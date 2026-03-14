import { useEffect, useRef } from "react";
import { FileText, Hash, Shield, X } from "lucide-react";

import type { Citation } from "@/types/api";

const TIER_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  High: { bg: "bg-emerald-50", text: "text-emerald-700", dot: "bg-emerald-500" },
  Moderate: { bg: "bg-amber-50", text: "text-amber-700", dot: "bg-amber-500" },
  Low: { bg: "bg-gray-100", text: "text-gray-600", dot: "bg-gray-400" },
};

interface CitationModalProps {
  citation: Citation;
  index: number;
  onClose: () => void;
}

export function CitationModal({ citation, index, onClose }: CitationModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  function handleOverlayClick(e: React.MouseEvent) {
    if (e.target === overlayRef.current) onClose();
  }

  const tier = citation.match_tier ?? "Moderate";
  const tierStyle = TIER_STYLES[tier] ?? TIER_STYLES["Moderate"]!;
  const rank = citation.rank ?? index + 1;

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
    >
      <div className="relative max-h-[80vh] w-full max-w-2xl overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-100 bg-gray-50 px-6 py-4">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">
              {rank}
            </span>
            <h3 className="text-sm font-semibold text-gray-900">
              Source #{rank}
            </h3>
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${tierStyle.bg} ${tierStyle.text}`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${tierStyle.dot}`} />
              {tier} Match
            </span>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-200 hover:text-gray-600"
          >
            <X size={18} />
          </button>
        </div>

        {/* Metadata */}
        <div className="grid grid-cols-2 gap-3 border-b border-gray-100 px-6 py-4 sm:grid-cols-3">
          <div className="flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-2">
            <FileText size={14} className="shrink-0 text-brand-500" />
            <div className="min-w-0">
              <div className="text-[10px] font-medium uppercase tracking-wide text-gray-400">
                Document
              </div>
              <div className="truncate text-xs font-medium text-gray-800">
                {citation.source}
              </div>
            </div>
          </div>

          {citation.section && (
            <div className="flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-2">
              <Hash size={14} className="shrink-0 text-brand-500" />
              <div className="min-w-0">
                <div className="text-[10px] font-medium uppercase tracking-wide text-gray-400">
                  Section
                </div>
                <div className="truncate text-xs font-medium text-gray-800">
                  {citation.section}
                </div>
              </div>
            </div>
          )}

          <div className="flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-2">
            <Shield size={14} className="shrink-0 text-brand-500" />
            <div className="min-w-0">
              <div className="text-[10px] font-medium uppercase tracking-wide text-gray-400">
                Match Rank
              </div>
              <div className="text-xs font-medium text-gray-800">
                #{rank} of {citation.rank != null ? "top results" : "results"}
              </div>
            </div>
          </div>
        </div>

        {/* Source Content */}
        <div className="overflow-y-auto px-6 py-4 max-h-[50vh]">
          <div className="mb-2 text-[10px] font-medium uppercase tracking-wide text-gray-400">
            Source Content
          </div>
          <div className="rounded-lg border border-gray-100 bg-gray-50 p-4 text-sm leading-relaxed text-gray-700 whitespace-pre-wrap">
            {citation.content}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-gray-100 bg-gray-50 px-6 py-3">
          <p className="text-[11px] text-gray-400">
            This passage was retrieved from your indexed safety documents using
            hybrid search (keyword + semantic similarity). Sources are ranked by
            best match — a &quot;High Match&quot; means this document closely aligns with
            your query.
          </p>
        </div>
      </div>
    </div>
  );
}
