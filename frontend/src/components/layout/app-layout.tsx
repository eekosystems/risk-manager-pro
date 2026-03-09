import { useState } from "react";

import { SettingsPage } from "@/components/settings/settings-page";
import { useOrganizationContext } from "@/context/organization-context";
import type { FunctionType } from "@/types/api";

import { HeaderBar } from "./header-bar";
import { LeftSidebar } from "./left-sidebar";
import { RightPanel } from "./right-panel";

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
  const { activeOrganization, organizations, setActiveOrganization } =
    useOrganizationContext();

  if (showSettings) {
    return (
      <div className="flex h-screen overflow-hidden bg-gray-50 font-sans">
        <SettingsPage onClose={() => setShowSettings(false)} />
      </div>
    );
  }

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
        }}
        onConversationSelect={setConversationId}
        activeOrganization={activeOrganization}
        organizations={organizations}
        onOrganizationSelect={(org) => {
          setActiveOrganization(org);
          setConversationId(null);
        }}
      />

      {/* Main Content */}
      <main aria-label="Chat workspace" className="flex flex-1 flex-col overflow-hidden">
        <HeaderBar onSettingsClick={() => setShowSettings(true)} />
        {children({ activeFunction, conversationId, setConversationId })}
      </main>

      {/* Right Panel */}
      <RightPanel
        isOpen={rightOpen}
        onToggle={() => setRightOpen(!rightOpen)}
        activeFunction={activeFunction}
        onFunctionSelect={(fn) => {
          setActiveFunction(fn);
          setConversationId(null);
        }}
      />
    </div>
  );
}
