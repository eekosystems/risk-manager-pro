import { useCallback, useEffect, useState } from "react";

import { AnalyticsDashboard } from "@/components/analytics/analytics-dashboard";
import { AuditLogPage } from "@/components/audit/audit-log-page";
import { RiskRegisterPage } from "@/components/risk-register/risk-register-page";
import { SearchModal } from "@/components/search/search-modal";
import { SettingsPage } from "@/components/settings/settings-page";
import { PHLWizard } from "@/components/workflows/phl-wizard";
import { SRAWizard } from "@/components/workflows/sra-wizard";
import { useOrganizationContext } from "@/hooks/use-organization-context";
import { useUserRole } from "@/hooks/use-user-role";
import type { FunctionType } from "@/types/api";

import { HeaderBar } from "./header-bar";
import { LeftSidebar } from "./left-sidebar";
import { RightPanel } from "./right-panel";

export type AppView = "chat" | "risk-register" | "phl-workflow" | "sra-workflow" | "analytics" | "audit-log";

const STORAGE_KEY = "rmp:layout:v1";
const VALID_VIEWS: ReadonlySet<AppView> = new Set([
  "chat",
  "risk-register",
  "phl-workflow",
  "sra-workflow",
  "analytics",
  "audit-log",
]);
const VALID_FUNCTIONS: ReadonlySet<FunctionType> = new Set([
  "phl",
  "sra",
  "system",
  "general",
  "risk_register",
]);

interface PersistedLayout {
  currentView: AppView;
  activeFunction: FunctionType;
  conversationId: string | null;
  leftOpen: boolean;
  rightOpen: boolean;
}

function loadPersistedLayout(): Partial<PersistedLayout> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const out: Partial<PersistedLayout> = {};
    if (typeof parsed.currentView === "string" && VALID_VIEWS.has(parsed.currentView as AppView)) {
      out.currentView = parsed.currentView as AppView;
    }
    if (
      typeof parsed.activeFunction === "string" &&
      VALID_FUNCTIONS.has(parsed.activeFunction as FunctionType)
    ) {
      out.activeFunction = parsed.activeFunction as FunctionType;
    }
    if (typeof parsed.conversationId === "string" || parsed.conversationId === null) {
      out.conversationId = parsed.conversationId as string | null;
    }
    if (typeof parsed.leftOpen === "boolean") out.leftOpen = parsed.leftOpen;
    if (typeof parsed.rightOpen === "boolean") out.rightOpen = parsed.rightOpen;
    return out;
  } catch {
    return {};
  }
}

interface AppLayoutProps {
  children: (props: {
    activeFunction: FunctionType;
    conversationId: string | null;
    setConversationId: (id: string | null) => void;
    onStartChat: (fn: FunctionType, seed?: string) => void;
    pendingInputSeed: string | null;
    clearPendingInputSeed: () => void;
  }) => React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const [persisted] = useState(loadPersistedLayout);
  const [leftOpen, setLeftOpen] = useState(persisted.leftOpen ?? true);
  const [rightOpen, setRightOpen] = useState(persisted.rightOpen ?? true);
  const [showSettings, setShowSettings] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [activeFunction, setActiveFunction] = useState<FunctionType>(
    persisted.activeFunction ?? "general",
  );
  const [conversationId, setConversationId] = useState<string | null>(
    persisted.conversationId ?? null,
  );
  const [currentView, setCurrentView] = useState<AppView>(persisted.currentView ?? "chat");
  const [pendingInputSeed, setPendingInputSeed] = useState<string | null>(null);
  const { activeOrganization, organizations, setActiveOrganization } =
    useOrganizationContext();
  const { canEdit } = useUserRole();

  const startChat = (fn: FunctionType, seed?: string) => {
    setActiveFunction(fn);
    setConversationId(null);
    setCurrentView("chat");
    setPendingInputSeed(seed ?? null);
  };

  const clearPendingInputSeed = useCallback(() => {
    setPendingInputSeed(null);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setShowSearch((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          currentView,
          activeFunction,
          conversationId,
          leftOpen,
          rightOpen,
        }),
      );
    } catch {
      // ignore storage failures (quota, privacy mode)
    }
  }, [currentView, activeFunction, conversationId, leftOpen, rightOpen]);

  const readOnlyNotice = (
    <div className="flex flex-1 items-center justify-center p-8">
      <div className="max-w-md rounded-lg border border-amber-200 bg-amber-50 p-6 text-center">
        <p className="text-sm font-semibold text-amber-900">Read-only access</p>
        <p className="mt-2 text-sm text-amber-700">
          This workflow requires analyst or admin permissions. Ask an admin to
          grant you access.
        </p>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50 font-sans">
      {/* Left Sidebar */}
      <LeftSidebar
        isOpen={leftOpen}
        onToggle={() => setLeftOpen(!leftOpen)}
        onConversationSelect={(id) => {
          setConversationId(id);
          setCurrentView("chat");
        }}
        activeOrganization={activeOrganization}
        organizations={organizations}
        onOrganizationSelect={(org) => {
          setActiveOrganization(org);
          setConversationId(null);
        }}
      />

      {/* Main Content */}
      <main aria-label="Main workspace" className="flex flex-1 flex-col overflow-hidden">
        <HeaderBar
          currentView={currentView}
          onSettingsClick={() => setShowSettings(true)}
          onSearchClick={() => setShowSearch(true)}
          onViewChange={setCurrentView}
        />
        {currentView === "analytics" ? (
          <AnalyticsDashboard />
        ) : currentView === "audit-log" ? (
          <AuditLogPage />
        ) : currentView === "risk-register" ? (
          <RiskRegisterPage onStartChatEntry={() => startChat("risk_register")} />
        ) : currentView === "phl-workflow" ? (
          canEdit ? (
            <PHLWizard
              onComplete={() => setCurrentView("risk-register")}
              onCancel={() => setCurrentView("chat")}
            />
          ) : (
            readOnlyNotice
          )
        ) : currentView === "sra-workflow" ? (
          canEdit ? (
            <SRAWizard
              onComplete={() => setCurrentView("risk-register")}
              onCancel={() => setCurrentView("chat")}
            />
          ) : (
            readOnlyNotice
          )
        ) : (
          children({
            activeFunction,
            conversationId,
            setConversationId,
            onStartChat: startChat,
            pendingInputSeed,
            clearPendingInputSeed,
          })
        )}
      </main>

      {/* Right Panel */}
      <RightPanel
        isOpen={rightOpen}
        onToggle={() => setRightOpen(!rightOpen)}
        activeFunction={activeFunction}
        onFunctionSelect={(fn) => {
          setActiveFunction(fn);
          setConversationId(null);
          setCurrentView("chat");
        }}
        currentView={currentView}
        onViewChange={setCurrentView}
      />

      {/* Settings Modal */}
      {showSettings && (
        <SettingsPage onClose={() => setShowSettings(false)} />
      )}

      <SearchModal
        open={showSearch}
        onClose={() => setShowSearch(false)}
        onSelectConversation={(id) => {
          setConversationId(id);
          setCurrentView("chat");
        }}
        onViewChange={setCurrentView}
      />
    </div>
  );
}
