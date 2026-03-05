import { AlertTriangle, BarChart3, ChevronRight, FileSearch, Shield } from "lucide-react";

import type { FunctionType } from "@/types/api";

interface TemplateItem {
  id: FunctionType;
  label: string;
  icon: typeof AlertTriangle;
}

const TEMPLATES: TemplateItem[] = [
  {
    id: "phl",
    label: "Construction Project PHL",
    icon: AlertTriangle,
  },
  {
    id: "sra",
    label: "Runway Closure SRA",
    icon: Shield,
  },
  {
    id: "system",
    label: "Taxiway Modification Analysis",
    icon: BarChart3,
  },
  {
    id: "phl",
    label: "Part 139 Compliance Check",
    icon: FileSearch,
  },
];

interface QuickStartTemplatesProps {
  activeFunction: FunctionType;
  onFunctionSelect: (fn: FunctionType) => void;
}

export function QuickStartTemplates({
  onFunctionSelect,
}: QuickStartTemplatesProps) {
  return (
    <>
      <h3 className="mb-3 text-[11px] font-bold uppercase tracking-wider text-gray-400">
        Quick Templates
      </h3>
      <div className="mb-6 flex flex-col gap-1.5">
        {TEMPLATES.map((t, i) => (
          <button
            key={`${t.id}-${i}`}
            onClick={() => onFunctionSelect(t.id)}
            className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-3 text-left transition-all hover:-translate-y-0.5 hover:border-brand-400 hover:shadow-md hover:shadow-brand-500/10"
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-500">
              <t.icon size={14} />
            </div>
            <span className="flex-1 text-[12px] font-medium text-gray-700">
              {t.label}
            </span>
            <ChevronRight size={12} className="text-gray-400" />
          </button>
        ))}
      </div>
    </>
  );
}
