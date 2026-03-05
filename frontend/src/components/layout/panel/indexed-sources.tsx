import { BookOpen } from "lucide-react";

interface SourceCategory {
  label: string;
  count: number;
}

const SOURCE_CATEGORIES: SourceCategory[] = [
  { label: "Safety Risk Assessments", count: 47 },
  { label: "FAA Regulations", count: 12 },
  { label: "Best Practice Guides", count: 23 },
];

export function IndexedSources() {
  return (
    <>
      <h3 className="mb-3 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-gray-400">
        <BookOpen size={12} />
        Indexed Sources
      </h3>
      <div className="mb-6 flex flex-col gap-2">
        {SOURCE_CATEGORIES.map((source) => (
          <div
            key={source.label}
            className="flex items-center gap-3 rounded-xl border border-gray-100 bg-white px-4 py-3"
          >
            <span className="text-xl font-bold text-brand-500">
              {source.count}
            </span>
            <span className="text-[13px] text-gray-600">{source.label}</span>
          </div>
        ))}
      </div>
    </>
  );
}
