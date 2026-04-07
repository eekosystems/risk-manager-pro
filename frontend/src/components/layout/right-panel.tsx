import { clsx } from "clsx";
import {
  AlertTriangle,
  BarChart3,
  Bot,
  ChevronRight,
  ScrollText,
  Shield,
  ShieldAlert,
  Workflow,
} from "lucide-react";

import { AiStatusCard } from "@/components/layout/panel/ai-status-card";
import { CoreFunctionsNav } from "@/components/layout/sidebar/core-functions-nav";
import { FUNCTIONS } from "@/constants/functions";
import type { FunctionType } from "@/types/api";

import type { AppView } from "./app-layout";

interface RightPanelProps {
  isOpen: boolean;
  onToggle: () => void;
  activeFunction: FunctionType;
  onFunctionSelect: (fn: FunctionType) => void;
  currentView: AppView;
  onViewChange: (view: AppView) => void;
}

export function RightPanel({
  isOpen,
  onToggle,
  activeFunction,
  onFunctionSelect,
  currentView,
  onViewChange,
}: RightPanelProps) {
  return (
    <aside
      aria-label="Functions and status"
      className={clsx(
        "relative flex flex-col border-l border-gray-200 bg-white transition-all duration-300",
        isOpen ? "w-[300px] min-w-[300px]" : "w-[60px] min-w-[60px]",
      )}
    >
      {/* Edge-centered toggle */}
      <button
        onClick={onToggle}
        aria-label={isOpen ? "Collapse panel" : "Expand panel"}
        className="absolute left-0 top-1/2 z-30 -translate-x-1/2 -translate-y-1/2 rounded-lg border border-gray-200 bg-white px-0.5 py-4 text-gray-400 shadow-md transition-colors hover:bg-brand-50 hover:text-brand-500"
      >
        <ChevronRight
          size={16}
          className={clsx("transition-transform", !isOpen && "rotate-180")}
        />
      </button>

      {isOpen ? (
        <div className="flex min-w-[300px] flex-col h-full overflow-y-auto px-3 py-4">
          <nav aria-label="Core functions">
            <CoreFunctionsNav
              activeFunction={activeFunction}
              onFunctionSelect={onFunctionSelect}
            />

            {/* Analytics + Risk Register + Audit Log nav */}
            <div className="mt-2 space-y-1">
              <button
                onClick={() => onViewChange("analytics")}
                className={clsx(
                  "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all",
                  currentView === "analytics"
                    ? "gradient-brand text-white shadow-md shadow-brand-500/30"
                    : "text-gray-600 hover:bg-brand-50 hover:text-brand-500",
                )}
              >
                <BarChart3 size={18} />
                Analytics
              </button>
              <button
                onClick={() => onViewChange("risk-register")}
                className={clsx(
                  "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all",
                  currentView === "risk-register"
                    ? "gradient-brand text-white shadow-md shadow-brand-500/30"
                    : "text-gray-600 hover:bg-brand-50 hover:text-brand-500",
                )}
              >
                <ShieldAlert size={18} />
                Risk Register
              </button>
              <button
                onClick={() => onViewChange("audit-log")}
                className={clsx(
                  "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all",
                  currentView === "audit-log"
                    ? "gradient-brand text-white shadow-md shadow-brand-500/30"
                    : "text-gray-600 hover:bg-brand-50 hover:text-brand-500",
                )}
              >
                <ScrollText size={18} />
                Audit Log
              </button>
            </div>

            {/* Workflows section */}
            <div className="mt-4">
              <div className="mb-1.5 flex items-center gap-2 px-3">
                <Workflow size={12} className="text-gray-400" />
                <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                  Workflows
                </span>
              </div>
              <div className="space-y-1">
                <button
                  onClick={() => onViewChange("phl-workflow")}
                  className={clsx(
                    "flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-all",
                    currentView === "phl-workflow"
                      ? "gradient-brand text-white shadow-md shadow-brand-500/30"
                      : "text-gray-600 hover:bg-brand-50 hover:text-brand-500",
                  )}
                >
                  <AlertTriangle size={16} />
                  PHL Wizard
                </button>
                <button
                  onClick={() => onViewChange("sra-workflow")}
                  className={clsx(
                    "flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-all",
                    currentView === "sra-workflow"
                      ? "gradient-brand text-white shadow-md shadow-brand-500/30"
                      : "text-gray-600 hover:bg-brand-50 hover:text-brand-500",
                  )}
                >
                  <Shield size={16} />
                  SRA Wizard
                </button>
              </div>
            </div>
          </nav>

          <div className="mt-auto px-2 pt-4">
            <AiStatusCard />
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center h-full py-3">
          {/* Collapsed nav icons */}
          <nav aria-label="Core functions" className="flex flex-col items-center gap-1">
            {FUNCTIONS.map((fn) => (
              <button
                key={fn.id}
                onClick={() => onFunctionSelect(fn.id)}
                aria-label={fn.name}
                title={fn.name}
                className={clsx(
                  "flex h-10 w-10 items-center justify-center rounded-lg transition-all",
                  activeFunction === fn.id && currentView === "chat"
                    ? "gradient-brand text-white shadow-md shadow-brand-500/30"
                    : "text-gray-400 hover:bg-brand-50 hover:text-brand-500",
                )}
              >
                <fn.icon size={20} />
              </button>
            ))}
          </nav>

          <div className="mx-3 my-3 h-px w-8 bg-gray-200" />

          {/* Analytics icon */}
          <button
            onClick={() => onViewChange("analytics")}
            aria-label="Analytics"
            title="Analytics"
            className={clsx(
              "flex h-10 w-10 items-center justify-center rounded-lg transition-all",
              currentView === "analytics"
                ? "gradient-brand text-white shadow-md shadow-brand-500/30"
                : "text-gray-400 hover:bg-brand-50 hover:text-brand-500",
            )}
          >
            <BarChart3 size={20} />
          </button>

          {/* Risk Register icon */}
          <button
            onClick={() => onViewChange("risk-register")}
            aria-label="Risk Register"
            title="Risk Register"
            className={clsx(
              "flex h-10 w-10 items-center justify-center rounded-lg transition-all",
              currentView === "risk-register"
                ? "gradient-brand text-white shadow-md shadow-brand-500/30"
                : "text-gray-400 hover:bg-brand-50 hover:text-brand-500",
            )}
          >
            <ShieldAlert size={20} />
          </button>

          {/* Audit Log icon */}
          <button
            onClick={() => onViewChange("audit-log")}
            aria-label="Audit Log"
            title="Audit Log"
            className={clsx(
              "flex h-10 w-10 items-center justify-center rounded-lg transition-all",
              currentView === "audit-log"
                ? "gradient-brand text-white shadow-md shadow-brand-500/30"
                : "text-gray-400 hover:bg-brand-50 hover:text-brand-500",
            )}
          >
            <ScrollText size={20} />
          </button>

          <div className="mx-3 my-3 h-px w-8 bg-gray-200" />

          {/* Workflow icons */}
          <button
            onClick={() => onViewChange("phl-workflow")}
            aria-label="PHL Wizard"
            title="PHL Wizard"
            className={clsx(
              "flex h-10 w-10 items-center justify-center rounded-lg transition-all",
              currentView === "phl-workflow"
                ? "gradient-brand text-white shadow-md shadow-brand-500/30"
                : "text-gray-400 hover:bg-brand-50 hover:text-brand-500",
            )}
          >
            <AlertTriangle size={20} />
          </button>
          <button
            onClick={() => onViewChange("sra-workflow")}
            aria-label="SRA Wizard"
            title="SRA Wizard"
            className={clsx(
              "flex h-10 w-10 items-center justify-center rounded-lg transition-all",
              currentView === "sra-workflow"
                ? "gradient-brand text-white shadow-md shadow-brand-500/30"
                : "text-gray-400 hover:bg-brand-50 hover:text-brand-500",
            )}
          >
            <Shield size={20} />
          </button>

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
