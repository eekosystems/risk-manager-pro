import { BookOpen, FileText } from "lucide-react";

interface SourceCategory {
  label: string;
  count: number;
  icon: typeof FileText;
}

const SOURCE_CATEGORIES: SourceCategory[] = [
  { label: "FAA Regulations", count: 847, icon: FileText },
  { label: "ICAO Standards", count: 523, icon: BookOpen },
  { label: "Company Procedures", count: 156, icon: FileText },
];

export function IndexedSources() {
  return (
    <>
      <h3 className="mb-3 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-gray-400">
        <BookOpen size={12} />
        Indexed Sources
      </h3>
      <div className="mb-6 flex flex-col gap-1.5">
        {SOURCE_CATEGORIES.map((source) => (
          <div
            key={source.label}
            className="flex items-center justify-between rounded-lg px-2 py-1.5"
          >
            <div className="flex items-center gap-2">
              <source.icon size={13} className="text-gray-400" />
              <span className="text-[12px] text-gray-600">{source.label}</span>
            </div>
            <span className="text-[11px] font-medium text-brand-500">
              {source.count.toLocaleString()}
            </span>
          </div>
        ))}
      </div>
    </>
  );
}
