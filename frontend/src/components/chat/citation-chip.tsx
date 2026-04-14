import { FileText } from "lucide-react";

import type { Citation } from "@/types/api";

interface CitationChipProps {
  citation: Citation;
  index: number;
  onClick: () => void;
}

export function CitationChip({ citation, index, onClick }: CitationChipProps) {
  const rank = citation.rank ?? index + 1;
  const name = citation.source.length > 40
    ? citation.source.slice(0, 37) + "..."
    : citation.source;

  return (
    <button
      type="button"
      onClick={onClick}
      className="citation-chip inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-gray-200 bg-gray-50 px-2.5 py-0.5 text-[11px] font-medium text-gray-700 transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
    >
      <sup className="text-[9px] font-semibold text-brand-600">[{rank}]</sup>
      <FileText size={10} className="shrink-0" />
      {name}
    </button>
  );
}
