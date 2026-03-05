import { clsx } from "clsx";

import { FUNCTIONS } from "@/constants/functions";
import type { FunctionType } from "@/types/api";

interface QuickStartTemplatesProps {
  activeFunction: FunctionType;
  onFunctionSelect: (fn: FunctionType) => void;
}

export function QuickStartTemplates({
  activeFunction,
  onFunctionSelect,
}: QuickStartTemplatesProps) {
  return (
    <>
      <h3 className="mb-3 text-[11px] font-bold uppercase tracking-wider text-gray-400">
        Quick Start
      </h3>
      <div className="mb-6 flex flex-col gap-2">
        {FUNCTIONS.map((t) => (
          <button
            key={t.id}
            onClick={() => onFunctionSelect(t.id)}
            className={clsx(
              "flex items-center gap-3 rounded-xl border p-3 text-left transition-all hover:-translate-y-0.5 hover:border-brand-400 hover:shadow-md hover:shadow-brand-500/10",
              activeFunction === t.id
                ? "border-brand-400 bg-brand-50"
                : "border-gray-200 bg-white",
            )}
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-500">
              <t.icon size={18} />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-gray-800">
                {t.title}
              </span>
              <span className="text-[11px] text-gray-400">
                {t.description}
              </span>
            </div>
          </button>
        ))}
      </div>
    </>
  );
}
