import { clsx } from "clsx";
import { Zap } from "lucide-react";

import { FUNCTIONS } from "@/constants/functions";
import type { FunctionType } from "@/types/api";

interface CoreFunctionsNavProps {
  activeFunction: FunctionType;
  onFunctionSelect: (fn: FunctionType) => void;
}

export function CoreFunctionsNav({
  activeFunction,
  onFunctionSelect,
}: CoreFunctionsNavProps) {
  return (
    <>
      <div className="mb-1 flex items-center px-2 text-[11px] font-bold uppercase tracking-wider text-gray-400">
        <Zap size={12} className="mr-1.5" />
        Core Functions
      </div>
      {FUNCTIONS.map((fn) => (
        <button
          key={fn.id}
          onClick={() => onFunctionSelect(fn.id)}
          aria-current={activeFunction === fn.id ? "page" : undefined}
          className={clsx(
            "nav-item-hover mb-1 flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left",
            activeFunction === fn.id && "bg-brand-50",
          )}
        >
          <div
            className={clsx(
              "flex h-9 w-9 items-center justify-center rounded-lg transition-all",
              activeFunction === fn.id
                ? "gradient-brand text-white shadow-md shadow-brand-500/30"
                : "bg-gray-100 text-brand-500",
            )}
          >
            <fn.icon size={18} />
          </div>
          <div className="flex flex-col">
            <span
              className={clsx(
                "text-sm font-semibold",
                activeFunction === fn.id
                  ? "text-brand-600"
                  : "text-gray-800",
              )}
            >
              {fn.name}
            </span>
            <span className="text-[11px] text-gray-400">
              {fn.description}
            </span>
          </div>
        </button>
      ))}
    </>
  );
}
