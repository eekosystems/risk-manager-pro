import { ExternalLink } from "lucide-react";

import type { Citation } from "@/types/api";

const TIER_DOT_COLOR: Record<string, string> = {
  High: "bg-emerald-500",
  Moderate: "bg-amber-500",
  Low: "bg-gray-400",
};

interface CitationChipProps {
  citation: Citation;
  index: number;
  onClick: () => void;
}

export function CitationChip({ citation, index, onClick }: CitationChipProps) {
  const rank = citation.rank ?? index + 1;
  const tier = citation.match_tier ?? "Moderate";
  const dotColor = TIER_DOT_COLOR[tier] ?? TIER_DOT_COLOR.Moderate;

  return (
    <button
      type="button"
      onClick={onClick}
      className="citation-chip inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-brand-200 bg-brand-50 px-2.5 py-0.5 text-[11px] font-medium text-brand-600 transition-colors hover:border-brand-400 hover:bg-brand-100"
    >
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotColor}`} />
      <ExternalLink size={10} />
      Source #{rank} — {citation.source}
    </button>
  );
}
