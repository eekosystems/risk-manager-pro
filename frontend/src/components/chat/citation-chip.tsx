import { ExternalLink } from "lucide-react";

import type { Citation } from "@/types/api";

interface CitationChipProps {
  citation: Citation;
  index: number;
}

export function CitationChip({ citation, index }: CitationChipProps) {
  return (
    <span className="citation-chip inline-flex items-center gap-1 rounded-full border border-brand-200 bg-brand-50 px-2.5 py-0.5 text-[11px] font-medium text-brand-600">
      <ExternalLink size={10} />
      [{index + 1}] {citation.source}
      {citation.section ? ` — ${citation.section}` : ""}
    </span>
  );
}
