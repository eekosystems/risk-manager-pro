import { useState } from "react";

import { RiskRegisterPage } from "@/components/risk-register/risk-register-page";
import { SettingsPage } from "@/components/settings/settings-page";
import { useOrganizationContext } from "@/hooks/use-organization-context";
import type { FunctionType } from "@/types/api";

import { HeaderBar } from "./header-bar";
import { LeftSidebar } from "./left-sidebar";
import { RightPanel } from "./right-panel";

export type AppView = "chat" | "risk-register";

interface AppLayoutProps {
  children: (props: {
    activeFunction: FunctionType;
    conversationId: string | null;
    setConversationId: (id: string | null) => void;
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

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50 font-sans">
      {/* Left Sidebar */}
      <LeftSidebar
        isOpen={leftOpen}
        onToggle={() => setLeftOpen(!leftOpen)}
        activeFunction={activeFunction}
        onFunctionSelect={(fn) => {
          setActiveFunction(fn);
          setConversationId(null);
          setCurrentView("chat");
        }}
        currentView={currentView}
        onViewChange={setCurrentView}
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
        />
        {currentView === "risk-register" ? (
          <RiskRegisterPage />
        ) : (
          children({ activeFunction, conversationId, setConversationId })
        )}
      </main>

      {/* Right Panel */}
      <RightPanel
        isOpen={rightOpen}
        onToggle={() => setRightOpen(!rightOpen)}
        onConversationSelect={(id) => {
          setConversationId(id);
          setCurrentView("chat");
        }}
      />

      {/* Settings Modal */}
      {showSettings && (
        <SettingsPage onClose={() => setShowSettings(false)} />
      )}
    </div>
  );
}
