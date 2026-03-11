import { useEffect, useState } from "react";
import { clsx } from "clsx";
import {
  Brain,
  Database,
  FileText,
  MessageSquareCode,
  Settings,
  Users,
  X,
} from "lucide-react";

import { RagSettingsTab } from "./tabs/rag-settings-tab";
import { IndexedFilesTab } from "./tabs/indexed-files-tab";
import { PromptsTab } from "./tabs/prompts-tab";
import { ModelPreferencesTab } from "./tabs/model-preferences-tab";
import { UsersRolesTab } from "./tabs/users-roles-tab";

type SettingsTab =
  | "rag"
  | "model"
  | "indexed-files"
  | "prompts"
  | "users";

interface TabDefinition {
  id: SettingsTab;
  label: string;
  icon: typeof Settings;
  description: string;
}

const TABS: TabDefinition[] = [
  {
    id: "rag",
    label: "RAG Settings",
    icon: Database,
    description: "Configure retrieval-augmented generation pipeline",
  },
  {
    id: "model",
    label: "Model Preferences",
    icon: Brain,
    description: "AI model selection and parameters",
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
  },
  {
    id: "users",
    label: "Users & Roles",
    icon: Users,
    description: "Manage team members and permissions",
  },
];

interface SettingsPageProps {
  onClose: () => void;
}

export function SettingsPage({ onClose }: SettingsPageProps) {
  const [activeTab, setActiveTab] = useState<SettingsTab>("rag");
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
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={clsx(
                    "flex items-center gap-3 rounded-xl px-4 py-3 text-left transition-all",
                    activeTab === tab.id
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
                        activeTab === tab.id
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
            {activeTab === "rag" && <RagSettingsTab />}
            {activeTab === "model" && <ModelPreferencesTab />}
            {activeTab === "indexed-files" && <IndexedFilesTab />}
            {activeTab === "prompts" && <PromptsTab />}
            {activeTab === "users" && <UsersRolesTab />}
          </div>
        </div>
      </div>
    </>
  );
}
