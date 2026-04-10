import { FileText } from "lucide-react";

import type { Citation } from "@/types/api";

const TIER_STYLES: Record<string, string> = {
  High: "border-emerald-200 bg-emerald-50 text-emerald-700",
  Moderate: "border-amber-200 bg-amber-50 text-amber-700",
  Low: "border-gray-200 bg-gray-50 text-gray-500",
};

interface CitationChipProps {
  citation: Citation;
  index: number;
  onClick: () => void;
}

export function CitationChip({ citation, onClick }: CitationChipProps) {
  const tier = citation.match_tier ?? "Moderate";
  const style = TIER_STYLES[tier] ?? TIER_STYLES.Moderate;

  // Truncate long filenames
  const name = citation.source.length > 40
    ? citation.source.slice(0, 37) + "..."
    : citation.source;

  return (
    <button
      type="button"
      onClick={onClick}
      className={`citation-chip inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors ${style}`}
    >
      <FileText size={10} className="shrink-0" />
      {name}
    </button>
  );
}
