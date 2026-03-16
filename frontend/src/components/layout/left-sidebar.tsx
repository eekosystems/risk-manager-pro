import { clsx } from "clsx";
import {
  AlertTriangle,
  ChevronRight,
  FileText,
  FolderSearch,
  Shield,
  ShieldAlert,
  User,
  Workflow,
} from "lucide-react";

import { IndexedSources } from "@/components/layout/panel/indexed-sources";
import { RecentDocuments } from "@/components/layout/panel/recent-documents";
import { CoreFunctionsNav } from "@/components/layout/sidebar/core-functions-nav";
import { OrganizationSwitcher } from "@/components/layout/sidebar/organization-switcher";
import { UserCard } from "@/components/layout/sidebar/user-card";
import { FUNCTIONS } from "@/constants/functions";
import type { FunctionType, OrganizationSummary } from "@/types/api";

import type { AppView } from "./app-layout";

interface LeftSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  activeFunction: FunctionType;
  onFunctionSelect: (fn: FunctionType) => void;
  currentView: AppView;
  onViewChange: (view: AppView) => void;
  activeOrganization: OrganizationSummary | null;
  organizations: OrganizationSummary[];
  onOrganizationSelect: (org: OrganizationSummary) => void;
}

export function LeftSidebar({
  isOpen,
  onToggle,
  activeFunction,
  onFunctionSelect,
  currentView,
  onViewChange,
  activeOrganization,
  organizations,
  onOrganizationSelect,
}: LeftSidebarProps) {
  return (
    <aside
      aria-label="Main navigation"
      className={clsx(
        "relative flex flex-col border-r border-gray-200 bg-white transition-all duration-300",
        isOpen ? "w-[300px] min-w-[300px]" : "w-[60px] min-w-[60px]",
      )}
    >
      {/* Edge-centered toggle */}
      <button
        onClick={onToggle}
        aria-label={isOpen ? "Collapse sidebar" : "Expand sidebar"}
        className="absolute right-0 top-1/2 z-30 translate-x-1/2 -translate-y-1/2 rounded-lg border border-gray-200 bg-white px-0.5 py-4 text-gray-400 shadow-md transition-colors hover:bg-brand-50 hover:text-brand-500"
      >
        <ChevronRight
          size={16}
          className={clsx("transition-transform", isOpen && "rotate-180")}
        />
      </button>

      {isOpen ? (
        <div className="flex min-w-[300px] flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-center border-b border-gray-100 px-5 py-4">
            <img src="/logo.webp" alt="Faith Group" className="h-auto w-[200px]" />
          </div>

          {activeOrganization && (
            <OrganizationSwitcher
              activeOrganization={activeOrganization}
              organizations={organizations}
              onOrganizationSelect={onOrganizationSelect}
            />
          )}

          <nav aria-label="Core functions" className="flex-1 overflow-y-auto px-3 py-4">
            <CoreFunctionsNav
              activeFunction={activeFunction}
              onFunctionSelect={onFunctionSelect}
            />

            {/* Risk Register nav button */}
            <div className="mt-2">
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

            <RecentDocuments />
            <IndexedSources />
          </nav>

          <UserCard />
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

          <div className="mx-3 my-3 h-px w-8 bg-gray-200" />

          {/* Documents icon */}
          <button
            onClick={onToggle}
            aria-label="Recent documents"
            title="Recent documents"
            className="flex h-10 w-10 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-brand-50 hover:text-brand-500"
          >
            <FileText size={20} />
          </button>

          {/* Sources icon */}
          <button
            onClick={onToggle}
            aria-label="Indexed sources"
            title="Indexed sources"
            className="flex h-10 w-10 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-brand-50 hover:text-brand-500"
          >
            <FolderSearch size={20} />
          </button>

          {/* User icon at bottom */}
          <div className="mt-auto">
            <button
              onClick={onToggle}
              aria-label="User profile"
              title="User profile"
              className="flex h-10 w-10 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-brand-50 hover:text-brand-500"
            >
              <User size={20} />
            </button>
          </div>
        </div>
      )}
    </aside>
  );
}
