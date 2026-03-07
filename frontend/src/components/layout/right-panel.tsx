import { clsx } from "clsx";
import { Bot, ChevronRight, FileText, FolderSearch, Rocket } from "lucide-react";

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
    <aside
      aria-label="Quick start and status"
      className={clsx(
        "flex flex-col border-l border-gray-200 bg-white transition-all duration-300",
        isOpen ? "w-[300px] min-w-[300px]" : "w-[60px] min-w-[60px]",
      )}
    >
      {isOpen ? (
        <div className="flex min-w-[300px] flex-col h-full overflow-y-auto px-5 py-5">
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm font-semibold text-gray-500">Quick Start</span>
            <button
              onClick={onToggle}
              aria-label="Collapse panel"
              className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-brand-50 hover:text-brand-500"
            >
              <ChevronRight size={16} />
            </button>
          </div>
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
      ) : (
        <div className="flex flex-col items-center h-full py-3">
          {/* Collapsed toggle */}
          <button
            onClick={onToggle}
            aria-label="Expand panel"
            className="mb-4 rounded-lg p-2 text-gray-400 transition-colors hover:bg-brand-50 hover:text-brand-500"
          >
            <ChevronRight size={18} className="rotate-180" />
          </button>

          {/* Collapsed section icons */}
          <nav className="flex flex-col items-center gap-1">
            <button
              onClick={onToggle}
              aria-label="Quick start templates"
              title="Quick start templates"
              className="flex h-10 w-10 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-brand-50 hover:text-brand-500"
            >
              <Rocket size={20} />
            </button>
            <button
              onClick={onToggle}
              aria-label="Recent documents"
              title="Recent documents"
              className="flex h-10 w-10 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-brand-50 hover:text-brand-500"
            >
              <FileText size={20} />
            </button>
            <button
              onClick={onToggle}
              aria-label="Indexed sources"
              title="Indexed sources"
              className="flex h-10 w-10 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-brand-50 hover:text-brand-500"
            >
              <FolderSearch size={20} />
            </button>
          </nav>

          {/* AI status at bottom */}
          <div className="mt-auto">
            <button
              onClick={onToggle}
              aria-label="AI status"
              title="AI status"
              className="flex h-10 w-10 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-brand-50 hover:text-brand-500"
            >
              <Bot size={20} />
            </button>
          </div>
        </div>
      )}
    </aside>
  );
}
