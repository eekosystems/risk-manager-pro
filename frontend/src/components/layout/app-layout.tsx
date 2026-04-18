import { useState } from "react";

import { AnalyticsDashboard } from "@/components/analytics/analytics-dashboard";
import { AuditLogPage } from "@/components/audit/audit-log-page";
import { RiskRegisterPage } from "@/components/risk-register/risk-register-page";
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

interface AppLayoutProps {
  children: (props: {
    activeFunction: FunctionType;
    conversationId: string | null;
    setConversationId: (id: string | null) => void;
    onStartChat: (fn: FunctionType) => void;
  }) => React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [activeFunction, setActiveFunction] = useState<FunctionType>("general");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [currentView, setCurrentView] = useState<AppView>("chat");
  const { activeOrganization, organizations, setActiveOrganization } =
    useOrganizationContext();
  const { canEdit } = useUserRole();

  const startChat = (fn: FunctionType) => {
    setActiveFunction(fn);
    setConversationId(null);
    setCurrentView("chat");
  };

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
    </div>
  );
}
