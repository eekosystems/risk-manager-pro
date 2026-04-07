import { clsx } from "clsx";
import {
  ChevronRight,
  FileText,
  MessageSquare,
  User,
} from "lucide-react";

import { RecentDocuments } from "@/components/layout/panel/recent-documents";
import { ConversationHistory } from "@/components/layout/sidebar/conversation-history";
import { OrganizationSwitcher } from "@/components/layout/sidebar/organization-switcher";
import { UserCard } from "@/components/layout/sidebar/user-card";
import type { OrganizationSummary } from "@/types/api";

interface LeftSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  onConversationSelect: (id: string) => void;
  activeOrganization: OrganizationSummary | null;
  organizations: OrganizationSummary[];
  onOrganizationSelect: (org: OrganizationSummary) => void;
}

export function LeftSidebar({
  isOpen,
  onToggle,
  onConversationSelect,
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

          <div className="flex-1 overflow-y-auto px-3 py-4">
            <ConversationHistory onConversationSelect={onConversationSelect} />
          </div>

          <div className="mt-auto border-t border-gray-100 px-3 pt-3">
            <RecentDocuments />
          </div>

          <UserCard />
        </div>
      ) : (
        <div className="flex flex-col items-center h-full py-3">
          {/* Collapsed section icons */}
          <nav className="flex flex-col items-center gap-1">
            <button
              onClick={onToggle}
              aria-label="Recent sessions"
              title="Recent sessions"
              className="flex h-10 w-10 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-brand-50 hover:text-brand-500"
            >
              <MessageSquare size={20} />
            </button>
            <button
              onClick={onToggle}
              aria-label="Recent documents"
              title="Recent documents"
              className="flex h-10 w-10 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-brand-50 hover:text-brand-500"
            >
              <FileText size={20} />
            </button>
          </nav>

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
