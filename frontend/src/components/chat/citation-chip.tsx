import { ExternalLink } from "lucide-react";

import type { Citation } from "@/types/api";

interface CitationChipProps {
  citation: Citation;
  index: number;
  onClick: () => void;
}

export function CitationChip({ citation, index, onClick }: CitationChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="citation-chip inline-flex cursor-pointer items-center gap-1 rounded-full border border-brand-200 bg-brand-50 px-2.5 py-0.5 text-[11px] font-medium text-brand-600 transition-colors hover:border-brand-400 hover:bg-brand-100"
    >
      <ExternalLink size={10} />
      [{index + 1}] {citation.source}
      {citation.section ? ` — ${citation.section}` : ""}
    </button>
  );
}
