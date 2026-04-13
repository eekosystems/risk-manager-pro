import { Search, Settings } from "lucide-react";

import { NotificationBell } from "@/components/notifications/notification-bell";
import { useUserRole } from "@/hooks/use-user-role";

import type { AppView } from "./app-layout";

interface HeaderBarProps {
  currentView?: AppView;
  onSettingsClick?: () => void;
  onViewChange?: (view: AppView) => void;
}

const VIEW_HEADERS: Record<AppView, { title: string; subtitle: string }> = {
  chat: {
    title: "Risk Manager Pro",
    subtitle: "AI-powered risk analysis using indexed Faith Group safety data",
  },
  "risk-register": {
    title: "Risk Register",
    subtitle: "Track hazards, assess risks, and manage mitigations",
  },
  "phl-workflow": {
    title: "PHL Wizard",
    subtitle: "Guided Preliminary Hazard List generation (AC 150/5200-37A Steps 1-2)",
  },
  "sra-workflow": {
    title: "SRA Wizard",
    subtitle: "Guided Safety Risk Assessment (AC 150/5200-37A Steps 3-5)",
  },
  analytics: {
    title: "Analytics Dashboard",
    subtitle: "Safety performance metrics and risk trends",
  },
  "audit-log": {
    title: "Audit Log",
    subtitle: "SOC 2 compliant activity log — all state-changing operations",
  },
};

export function HeaderBar({ currentView = "chat", onSettingsClick, onViewChange }: HeaderBarProps) {
  const header = VIEW_HEADERS[currentView];
  const { isAdmin } = useUserRole();

  return (
    <div className="flex items-center justify-between border-b border-gray-200 bg-white px-8 py-4">
      <div className="flex flex-col">
        <h1 className="text-[22px] font-bold text-slate-900">
          {header.title}
        </h1>
        <p className="text-[13px] text-slate-500">
          {header.subtitle}
        </p>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5">
          <Search size={16} className="text-gray-400" />
          <span className="text-sm text-gray-400">Search conversations...</span>
          <kbd className="ml-4 rounded-md border border-gray-200 bg-white px-1.5 py-0.5 text-[11px] font-medium text-gray-400">
            ⌘K
          </kbd>
        </div>
        <NotificationBell onNavigate={onViewChange} />
        {isAdmin && (
          <button
            onClick={onSettingsClick}
            className="rounded-xl border border-gray-200 p-2.5 text-gray-400 transition-colors hover:bg-gray-50 hover:text-gray-600"
            aria-label="Settings"
          >
            <Settings size={18} />
          </button>
        )}
      </div>
    </div>
  );
}
