import { useEffect, useState } from "react";
import { clsx } from "clsx";
import {
  Brain,
  Database,
  FileText,
  MessageSquareCode,
  Building2,
  Settings,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from "lucide-react";

import { RagSettingsTab } from "./tabs/rag-settings-tab";
import { IndexedFilesTab } from "./tabs/indexed-files-tab";
import { PromptsTab } from "./tabs/prompts-tab";
import { ModelPreferencesTab } from "./tabs/model-preferences-tab";
import { QaqcSettingsTab } from "./tabs/qaqc-settings-tab";
import { UsersRolesTab } from "./tabs/users-roles-tab";
import { FeedbackTab } from "./tabs/feedback-tab";
import { ClientAccountsTab } from "./tabs/client-accounts-tab";

import { useUserRole } from "@/hooks/use-user-role";

type SettingsTab =
  | "rag"
  | "model"
  | "indexed-files"
  | "prompts"
  | "users"
  | "qaqc"
  | "feedback"
  | "accounts";

interface TabDefinition {
  id: SettingsTab;
  label: string;
  icon: typeof Settings;
  description: string;
  /** Changes AI behaviour or tenancy across accounts — Faith Group only. */
  platformAdminOnly?: boolean;
  /** Account-level administration, available to a client's own admin. */
  orgAdminOnly?: boolean;
}

const TABS: TabDefinition[] = [
  {
    id: "rag",
    label: "RAG Settings",
    icon: Database,
    description: "Configure retrieval-augmented generation pipeline",
    platformAdminOnly: true,
  },
  {
    id: "model",
    label: "Model Preferences",
    icon: Brain,
    description: "AI model selection and parameters",
    platformAdminOnly: true,
  },
  {
    id: "indexed-files",
    label: "Indexed Files",
    icon: FileText,
    description: "Manage documents in the search index",
  },
  {
    id: "prompts",
    label: "Prompts",
    icon: MessageSquareCode,
    description: "System prompt and function-specific prompts",
    platformAdminOnly: true,
  },
  {
    id: "users",
    label: "Users & Roles",
    icon: Users,
    description: "Manage team members and permissions",
    orgAdminOnly: true,
  },
  {
    id: "qaqc",
    label: "QA/QC Reviewers",
    icon: ShieldCheck,
    description: "Configure QA/QC notification recipients",
    platformAdminOnly: true,
  },
  {
    id: "accounts",
    label: "Client Accounts",
    icon: Building2,
    description: "Create client environments and assign their folders",
    platformAdminOnly: true,
  },
  {
    id: "feedback",
    label: "Feedback & Training",
    icon: Sparkles,
    description: "Review user feedback and curate application guidance",
    platformAdminOnly: true,
  },
];

interface SettingsPageProps {
  onClose: () => void;
}

export function SettingsPage({ onClose }: SettingsPageProps) {
  const [activeTab, setActiveTab] = useState<SettingsTab | null>(null);
  const { isPlatformAdmin, isAdmin } = useUserRole();
  // Client users see their files and nothing else. Their own account admin
  // additionally gets Users & Roles so they can add colleagues.
  const visibleTabs = TABS.filter((tab) => {
    if (tab.platformAdminOnly) return isPlatformAdmin;
    if (tab.orgAdminOnly) return isAdmin;
    return true;
  });
  // The first tab differs by role — a client opens on Indexed Files, not on
  // the RAG settings they cannot see. Resolved after the role loads.
  const currentTab: SettingsTab | undefined =
    activeTab && visibleTabs.some((t) => t.id === activeTab)
      ? activeTab
      : visibleTabs[0]?.id;
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Trigger enter animation
    requestAnimationFrame(() => setIsVisible(true));
  }, []);

  function handleClose() {
    setIsVisible(false);
    setTimeout(onClose, 200);
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className={clsx(
          "fixed inset-0 z-40 bg-black/40 backdrop-blur-sm transition-opacity duration-200",
          isVisible ? "opacity-100" : "opacity-0",
        )}
        onClick={handleClose}
      />

      {/* Modal */}
      <div
        className={clsx(
          "fixed inset-y-8 left-1/2 z-50 flex w-full max-w-5xl -translate-x-1/2 flex-col overflow-hidden rounded-2xl border border-gray-200 bg-gray-50 shadow-2xl transition-all duration-200",
          isVisible
            ? "scale-100 opacity-100"
            : "scale-95 opacity-0",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 bg-white px-8 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl gradient-brand">
              <Settings size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900">Settings</h1>
              <p className="text-[13px] text-slate-500">
                Configure your risk management platform
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="rounded-xl border border-gray-200 p-2.5 text-gray-400 transition-colors hover:bg-gray-50 hover:text-gray-600"
            aria-label="Close settings"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* Tab sidebar */}
          <nav className="w-[260px] min-w-[260px] border-r border-gray-200 bg-white p-4">
            <div className="flex flex-col gap-1">
              {visibleTabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={clsx(
                    "flex items-center gap-3 rounded-xl px-4 py-3 text-left transition-all",
                    currentTab === tab.id
                      ? "gradient-brand text-white shadow-md shadow-brand-500/20"
                      : "text-gray-600 hover:bg-gray-50",
                  )}
                >
                  <tab.icon size={18} />
                  <div className="flex flex-col">
                    <span className="text-sm font-semibold">{tab.label}</span>
                    <span
                      className={clsx(
                        "text-[11px]",
                        currentTab === tab.id
                          ? "text-white/70"
                          : "text-gray-400",
                      )}
                    >
                      {tab.description}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </nav>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto p-8">
            {currentTab === "rag" && <RagSettingsTab />}
            {currentTab === "model" && <ModelPreferencesTab />}
            {currentTab === "indexed-files" && <IndexedFilesTab />}
            {currentTab === "prompts" && <PromptsTab />}
            {currentTab === "users" && <UsersRolesTab />}
            {currentTab === "qaqc" && <QaqcSettingsTab />}
            {currentTab === "feedback" && isPlatformAdmin && <FeedbackTab />}
            {currentTab === "accounts" && isPlatformAdmin && <ClientAccountsTab />}
          </div>
        </div>
      </div>
    </>
  );
}
