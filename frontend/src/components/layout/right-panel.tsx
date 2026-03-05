import { clsx } from "clsx";
import { ChevronRight } from "lucide-react";

import { AiStatusCard } from "@/components/layout/panel/ai-status-card";
import { IndexedSources } from "@/components/layout/panel/indexed-sources";
import { QuickStartTemplates } from "@/components/layout/panel/quick-start-templates";
import { RecentDocuments } from "@/components/layout/panel/recent-documents";
import type { FunctionType } from "@/types/api";

interface RightPanelProps {
  isOpen: boolean;
  onToggle: () => void;
  activeFunction: FunctionType;
  onFunctionSelect: (fn: FunctionType) => void;
}

export function RightPanel({
  isOpen,
  onToggle,
  activeFunction,
  onFunctionSelect,
}: RightPanelProps) {
  return (
    <>
      <button
        onClick={onToggle}
        aria-label={isOpen ? "Collapse panel" : "Expand panel"}
        className={clsx(
          "fixed top-1/2 z-30 -translate-y-1/2 rounded-l-lg border border-r-0 border-gray-200 bg-white p-1.5 text-gray-400 shadow-sm transition-all hover:bg-brand-50 hover:text-brand-500",
          isOpen ? "right-[299px]" : "right-0",
        )}
      >
        <ChevronRight
          size={16}
          className={clsx("transition-transform", !isOpen && "rotate-180")}
        />
      </button>

      <aside
        aria-label="Quick start and status"
        className={clsx(
          "flex flex-col border-l border-gray-200 bg-white transition-all duration-300",
          isOpen ? "w-[300px] min-w-[300px]" : "w-0 min-w-0 overflow-hidden",
        )}
      >
        <div className="flex min-w-[300px] flex-col h-full overflow-y-auto px-5 py-5">
          <QuickStartTemplates
            activeFunction={activeFunction}
            onFunctionSelect={onFunctionSelect}
          />
          <RecentDocuments />
          <IndexedSources />
          <div className="mt-auto">
            <AiStatusCard />
          </div>
        </div>
      </aside>
    </>
  );
}
