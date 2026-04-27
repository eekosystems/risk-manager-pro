import { useEffect, useState } from "react";
import { Loader2, Save, UserCheck } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { getOrganizationMembers } from "@/api/organizations";
import {
  getSettingsByCategory,
  updateQaqcSettings,
  type DeliveryMode,
  type DigestFrequency,
  type QaqcSettings,
} from "@/api/settings";
import { Button } from "@/components/ui/button";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { useOrganizationContext } from "@/hooks/use-organization-context";
import { useToast } from "@/hooks/use-toast";

const DEFAULT_QAQC: QaqcSettings = {
  reviewer_user_ids: [],
  notify_on_chat: true,
  notify_on_risk_created: true,
  notify_on_risk_updated: true,
  notify_on_mitigation_created: true,
  notify_on_document_indexed: false,
  delivery_mode: "both",
  digest_frequency: "immediate",
  digest_send_hour_utc: 13,
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
        <h3 className="mb-3 flex items-center gap-1.5 text-sm font-bold text-slate-700">
          Select Reviewers
          <InfoTooltip
            label="About reviewers"
            content={
              <>
                The team members who receive QA/QC notifications. Reviewers
                see every AI-generated output and risk-register change so
                they can audit quality. Only members of the active
                organization can be selected — add them in Users &amp;
                Roles first if a name is missing.
              </>
            }
          />
        </h3>
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

      {/* Delivery method */}
      <div>
        <h3 className="mb-3 flex items-center gap-1.5 text-sm font-bold text-slate-700">
          Delivery Method
          <InfoTooltip
            label="About delivery method"
            content={
              <>
                Where reviewers receive QA/QC alerts.{" "}
                <strong>In-app</strong> shows a notification badge in the
                app's bell icon. <strong>Email</strong> sends a message to
                the reviewer's organization email address.{" "}
                <strong>Both</strong> sends to in-app + email so nothing is
                missed.
              </>
            }
          />
        </h3>
        <div className="grid grid-cols-3 gap-2">
          {(["in_app", "email", "both"] as DeliveryMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => setConfig((prev) => ({ ...prev, delivery_mode: mode }))}
              className={`rounded-xl border px-3 py-3 text-sm font-medium transition-all ${
                config.delivery_mode === mode
                  ? "border-brand-300 bg-brand-50 text-brand-700"
                  : "border-gray-200 bg-white text-slate-700 hover:border-gray-300"
              }`}
            >
              {mode === "in_app" && "In-app only"}
              {mode === "email" && "Email only"}
              {mode === "both" && "In-app + Email"}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Email delivery uses Azure Communication Services with managed identity authentication.
        </p>
      </div>

      {/* Digest frequency */}
      <div>
        <h3 className="mb-3 flex items-center gap-1.5 text-sm font-bold text-slate-700">
          Digest Frequency
          <InfoTooltip
            label="About digest frequency"
            content={
              <>
                How often reviewers are notified. <strong>Immediate</strong>{" "}
                sends one alert per event as it happens.{" "}
                <strong>Daily</strong> bundles every event from the past 24
                hours into one summary at the chosen UTC hour.{" "}
                <strong>Weekly</strong> does the same on a 7-day cadence.
                Use a digest if reviewers are getting too many individual
                alerts.
              </>
            }
          />
        </h3>
        <div className="grid grid-cols-3 gap-2">
          {(["immediate", "daily", "weekly"] as DigestFrequency[]).map((freq) => (
            <button
              key={freq}
              onClick={() => setConfig((prev) => ({ ...prev, digest_frequency: freq }))}
              className={`rounded-xl border px-3 py-3 text-sm font-medium transition-all ${
                config.digest_frequency === freq
                  ? "border-brand-300 bg-brand-50 text-brand-700"
                  : "border-gray-200 bg-white text-slate-700 hover:border-gray-300"
              }`}
            >
              {freq.charAt(0).toUpperCase() + freq.slice(1)}
            </button>
          ))}
        </div>
        {config.digest_frequency !== "immediate" && (
          <div className="mt-3 flex items-center gap-3">
            <label className="text-xs font-medium text-slate-600">
              Send hour (UTC):
            </label>
            <input
              type="number"
              min={0}
              max={23}
              value={config.digest_send_hour_utc}
              onChange={(e) =>
                setConfig((prev) => ({
                  ...prev,
                  digest_send_hour_utc: Math.max(0, Math.min(23, Number(e.target.value))),
                }))
              }
              className="w-20 rounded-lg border border-gray-200 px-3 py-1 text-sm"
            />
            <span className="text-xs text-slate-400">
              13 UTC ≈ 08:00 US Central
            </span>
          </div>
        )}
      </div>

      {/* Notification toggles */}
      <div>
        <h3 className="mb-3 flex items-center gap-1.5 text-sm font-bold text-slate-700">
          Notification Triggers
          <InfoTooltip
            label="About notification triggers"
            content={
              <>
                Which kinds of events generate a QA/QC alert. Turn off any
                event type that's too noisy for reviewers to be useful —
                for example, document indexing is off by default because
                it can fire many times during a bulk upload.
              </>
            }
          />
        </h3>
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
          <ToggleRow
            label="Risk Entry Updated"
            description="Notify when a risk entry's status, severity, or other fields change"
            checked={config.notify_on_risk_updated}
            onChange={(v) => setConfig((prev) => ({ ...prev, notify_on_risk_updated: v }))}
          />
          <ToggleRow
            label="Mitigation Created"
            description="Notify when a new mitigation is added to a risk"
            checked={config.notify_on_mitigation_created}
            onChange={(v) =>
              setConfig((prev) => ({ ...prev, notify_on_mitigation_created: v }))
            }
          />
          <ToggleRow
            label="Document Indexed"
            description="Notify when a new document finishes indexing into the RAG corpus"
            checked={config.notify_on_document_indexed}
            onChange={(v) =>
              setConfig((prev) => ({ ...prev, notify_on_document_indexed: v }))
            }
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
