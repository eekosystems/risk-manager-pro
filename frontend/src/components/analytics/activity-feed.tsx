import { formatDistanceToNow } from "date-fns";
import { Activity, Loader2 } from "lucide-react";

import { useRecentActivity } from "@/hooks/use-analytics";

const ACTION_LABELS: Record<string, string> = {
  "risk.created": "Risk Created",
  "risk.updated": "Risk Updated",
  "risk.deleted": "Risk Deleted",
  "mitigation.created": "Mitigation Added",
  "mitigation.updated": "Mitigation Updated",
  "mitigation.deleted": "Mitigation Deleted",
  "message_sent": "Message Sent",
  "conversation_deleted": "Conversation Deleted",
  "document.uploaded": "Document Uploaded",
  "document.deleted": "Document Deleted",
  "organization.created": "Organization Created",
  "organization.updated": "Organization Updated",
  "member_added": "Member Added",
  "member_role_updated": "Role Updated",
  "member_removed": "Member Removed",
  "rag.updated": "RAG Settings Updated",
  "model.updated": "Model Settings Updated",
  "prompts.updated": "Prompts Updated",
};

const OUTCOME_STYLES: Record<string, string> = {
  success: "bg-green-50 text-green-600",
  failure: "bg-red-50 text-red-600",
  denied: "bg-amber-50 text-amber-600",
};

export function ActivityFeed() {
  const { data: entries, isLoading } = useRecentActivity(15);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 size={20} className="animate-spin text-brand-500" />
      </div>
    );
  }

  if (!entries || entries.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-gray-400">
        No recent activity
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {entries.map((entry) => {
        const label = ACTION_LABELS[entry.action] ?? entry.action;
        const outcomeCls = OUTCOME_STYLES[entry.outcome] ?? OUTCOME_STYLES.success;
        return (
          <div
            key={entry.id}
            className="flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-gray-50"
          >
            <Activity size={14} className="shrink-0 text-gray-300" />
            <div className="min-w-0 flex-1">
              <span className="text-sm font-medium text-slate-700">{label}</span>
              {entry.resource_type && (
                <span className="ml-1.5 text-xs text-slate-400">
                  ({entry.resource_type})
                </span>
              )}
            </div>
            <span
              className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${outcomeCls}`}
            >
              {entry.outcome}
            </span>
            <span className="shrink-0 text-[11px] text-slate-400">
              {formatDistanceToNow(new Date(entry.timestamp), { addSuffix: true })}
            </span>
          </div>
        );
      })}
    </div>
  );
}
