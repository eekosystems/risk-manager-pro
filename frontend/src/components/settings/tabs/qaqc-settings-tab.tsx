import { useEffect, useState } from "react";
import { Loader2, Save, UserCheck } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { getOrganizationMembers } from "@/api/organizations";
import {
  getSettingsByCategory,
  updateQaqcSettings,
  type QaqcSettings,
} from "@/api/settings";
import { Button } from "@/components/ui/button";
import { useOrganizationContext } from "@/hooks/use-organization-context";
import { useToast } from "@/hooks/use-toast";

const DEFAULT_QAQC: QaqcSettings = {
  reviewer_user_ids: [],
  notify_on_chat: true,
  notify_on_risk_created: true,
};

export function QaqcSettingsTab() {
  const { activeOrganization } = useOrganizationContext();
  const { addToast } = useToast();
  const [config, setConfig] = useState<QaqcSettings>(DEFAULT_QAQC);
  const [isSaving, setIsSaving] = useState(false);

  const orgId = activeOrganization?.id;

  const { data: members } = useQuery({
    queryKey: ["organization-members", orgId],
    queryFn: () => getOrganizationMembers(orgId!),
    enabled: !!orgId,
  });

  const { data: settingsData, isLoading } = useQuery({
    queryKey: ["settings", "qaqc"],
    queryFn: () => getSettingsByCategory<QaqcSettings>("qaqc"),
  });

  useEffect(() => {
    if (settingsData?.settings) {
      setConfig({
        ...DEFAULT_QAQC,
        ...settingsData.settings,
      });
    }
  }, [settingsData]);

  async function handleSave() {
    setIsSaving(true);
    try {
      await updateQaqcSettings(config);
      addToast("QA/QC settings saved", "success");
    } catch {
      addToast("Failed to save QA/QC settings", "error");
    } finally {
      setIsSaving(false);
    }
  }

  function toggleReviewer(userId: string) {
    setConfig((prev) => {
      const ids = prev.reviewer_user_ids.includes(userId)
        ? prev.reviewer_user_ids.filter((id) => id !== userId)
        : [...prev.reviewer_user_ids, userId];
      return { ...prev, reviewer_user_ids: ids };
    });
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 size={20} className="animate-spin text-brand-500" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-bold text-slate-900">QA/QC Reviewers</h2>
        <p className="mt-1 text-sm text-slate-500">
          Designated FG Ops Safety staff who receive automatic notifications on all
          system outputs for quality assurance oversight.
        </p>
      </div>

      {/* Reviewer selection */}
      <div>
        <h3 className="mb-3 text-sm font-bold text-slate-700">Select Reviewers</h3>
        <div className="space-y-2">
          {members && members.length > 0 ? (
            members.map((member) => {
              const isSelected = config.reviewer_user_ids.includes(member.user_id);
              return (
                <button
                  key={member.user_id}
                  onClick={() => toggleReviewer(member.user_id)}
                  className={`flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all ${
                    isSelected
                      ? "border-brand-300 bg-brand-50"
                      : "border-gray-200 bg-white hover:border-gray-300"
                  }`}
                >
                  <div
                    className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                      isSelected ? "bg-brand-500 text-white" : "bg-gray-100 text-gray-400"
                    }`}
                  >
                    <UserCheck size={14} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-slate-800">
                      {member.display_name}
                    </div>
                    <div className="text-xs text-slate-400">{member.email}</div>
                  </div>
                  <div
                    className={`h-4 w-4 rounded-full border-2 ${
                      isSelected
                        ? "border-brand-500 bg-brand-500"
                        : "border-gray-300 bg-white"
                    }`}
                  >
                    {isSelected && (
                      <svg viewBox="0 0 16 16" className="h-full w-full text-white">
                        <path
                          fill="currentColor"
                          d="M6.5 11.5L3 8l1-1 2.5 2.5L11 5l1 1z"
                        />
                      </svg>
                    )}
                  </div>
                </button>
              );
            })
          ) : (
            <p className="text-sm text-gray-400">
              No organization members found. Add members in Users &amp; Roles first.
            </p>
          )}
        </div>
      </div>

      {/* Notification toggles */}
      <div>
        <h3 className="mb-3 text-sm font-bold text-slate-700">Notification Triggers</h3>
        <div className="space-y-3">
          <ToggleRow
            label="AI Chat Responses"
            description="Notify when AI generates a response in any conversation"
            checked={config.notify_on_chat}
            onChange={(v) => setConfig((prev) => ({ ...prev, notify_on_chat: v }))}
          />
          <ToggleRow
            label="Risk Entry Created"
            description="Notify when a new risk entry is saved to the register"
            checked={config.notify_on_risk_created}
            onChange={(v) => setConfig((prev) => ({ ...prev, notify_on_risk_created: v }))}
          />
        </div>
      </div>

      {/* Save */}
      <div className="flex justify-end border-t border-gray-200 pt-4">
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? (
            <Loader2 size={16} className="mr-2 animate-spin" />
          ) : (
            <Save size={16} className="mr-2" />
          )}
          Save Settings
        </Button>
      </div>
    </div>
  );
}

interface ToggleRowProps {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

function ToggleRow({ label, description, checked, onChange }: ToggleRowProps) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-4 py-3">
      <div>
        <div className="text-sm font-medium text-slate-800">{label}</div>
        <div className="text-xs text-slate-400">{description}</div>
      </div>
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
          checked ? "bg-brand-500" : "bg-gray-200"
        }`}
      >
        <span
          className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${
            checked ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </button>
    </div>
  );
}
