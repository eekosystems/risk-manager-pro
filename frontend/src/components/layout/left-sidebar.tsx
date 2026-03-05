import { clsx } from "clsx";

import { ConversationHistory } from "@/components/layout/sidebar/conversation-history";
import { CoreFunctionsNav } from "@/components/layout/sidebar/core-functions-nav";
import { OrganizationSwitcher } from "@/components/layout/sidebar/organization-switcher";
import { SidebarToggle } from "@/components/layout/sidebar/sidebar-toggle";
import { UserCard } from "@/components/layout/sidebar/user-card";
import type { FunctionType, OrganizationSummary } from "@/types/api";

interface LeftSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  activeFunction: FunctionType;
  onFunctionSelect: (fn: FunctionType) => void;
  onConversationSelect: (id: string) => void;
  activeOrganization: OrganizationSummary | null;
  organizations: OrganizationSummary[];
  onOrganizationSelect: (org: OrganizationSummary) => void;
}

export function LeftSidebar({
  isOpen,
  onToggle,
  activeFunction,
  onFunctionSelect,
  onConversationSelect,
  activeOrganization,
  organizations,
  onOrganizationSelect,
}: LeftSidebarProps) {
  return (
    <>
      <SidebarToggle isOpen={isOpen} onToggle={onToggle} />

      <aside
        aria-label="Main navigation"
        className={clsx(
          "relative flex flex-col border-r border-gray-200 bg-white transition-all duration-300",
          isOpen ? "w-[300px] min-w-[300px]" : "w-0 min-w-0 overflow-hidden",
        )}
      >
        <div className="flex min-w-[300px] flex-col h-full">
          {/* Logo */}
          <div className="flex items-center gap-3 border-b border-gray-100 px-5 py-4">
            <img src="/logo.webp" alt="Logo" className="h-9 w-9" />
            <div className="flex items-baseline gap-1.5">
              <span className="text-lg font-bold text-gray-900">
                Risk Manager
              </span>
              <span className="text-sm font-bold text-brand-500">PRO</span>
            </div>
            <span className="ml-auto rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-bold text-brand-600">
              v0.1
            </span>
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
            <ConversationHistory onConversationSelect={onConversationSelect} />
          </nav>

          <UserCard />
        </div>
      </aside>
    </>
  );
}
