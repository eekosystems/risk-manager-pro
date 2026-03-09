import { clsx } from "clsx";
import { ChevronRight, FileText, FolderSearch, User } from "lucide-react";

import { IndexedSources } from "@/components/layout/panel/indexed-sources";
import { RecentDocuments } from "@/components/layout/panel/recent-documents";
import { CoreFunctionsNav } from "@/components/layout/sidebar/core-functions-nav";
import { OrganizationSwitcher } from "@/components/layout/sidebar/organization-switcher";
import { UserCard } from "@/components/layout/sidebar/user-card";
import { FUNCTIONS } from "@/constants/functions";
import type { FunctionType, OrganizationSummary } from "@/types/api";

interface LeftSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  activeFunction: FunctionType;
  onFunctionSelect: (fn: FunctionType) => void;
  activeOrganization: OrganizationSummary | null;
  organizations: OrganizationSummary[];
  onOrganizationSelect: (org: OrganizationSummary) => void;
}

export function LeftSidebar({
  isOpen,
  onToggle,
  activeFunction,
  onFunctionSelect,
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
                  activeFunction === fn.id
                    ? "gradient-brand text-white shadow-md shadow-brand-500/30"
                    : "text-gray-400 hover:bg-brand-50 hover:text-brand-500",
                )}
              >
                <fn.icon size={20} />
              </button>
            ))}
          </nav>

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
