import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Database, RefreshCw, Zap } from "lucide-react";
import { useState } from "react";

import { getHealthStatus, type HealthStatus } from "@/api/health";

function formatTimeAgo(isoString: string): string {
  const seconds = Math.floor(
    (Date.now() - new Date(isoString).getTime()) / 1000,
  );
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

function checkLabel(value: string): { text: string; color: string } {
  switch (value) {
    case "ok":
      return { text: "Active", color: "text-green-400" };
    case "not_configured":
      return { text: "Not Configured", color: "text-slate-500" };
    default:
      return { text: "Unavailable", color: "text-red-400" };
  }
}

function statusLabel(health: HealthStatus | undefined): {
  text: string;
  dotColor: string;
} {
  if (!health) return { text: "Checking...", dotColor: "bg-slate-400" };
  switch (health.status) {
    case "healthy":
      return { text: "Connected", dotColor: "bg-green-400" };
    case "degraded":
      return { text: "Degraded", dotColor: "bg-yellow-400" };
    default:
      return { text: "Unavailable", dotColor: "bg-red-400" };
  }
}

export function AiStatusCard() {
  const [expanded, setExpanded] = useState(false);

  const { data: health } = useQuery<HealthStatus>({
    queryKey: ["health"],
    queryFn: getHealthStatus,
    refetchInterval: 30_000,
  });

  const aiCheck = health?.checks?.openai;
  const searchCheck = health?.checks?.search;
  const status = statusLabel(health);
  const aiLabel = aiCheck ? checkLabel(aiCheck) : null;
  const searchLabel = searchCheck ? checkLabel(searchCheck) : null;

  if (!expanded) {
    return (
      <button
        type="button"
        onClick={() => setExpanded(true)}
        aria-expanded={false}
        aria-label={`AI Status: ${status.text}. Click to expand.`}
        className="flex w-full items-center gap-2 rounded-xl bg-slate-800 px-3 py-2 text-left transition hover:bg-slate-700/80"
      >
        <div className={`h-2 w-2 shrink-0 rounded-full ${status.dotColor}`} />
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-300">
          AI {status.text}
        </span>
        <ChevronDown size={14} className="ml-auto text-slate-400" />
      </button>
    );
  }

  return (
    <div className="rounded-xl bg-slate-800 p-4" role="status">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
          AI Status
        </span>
        <button
          type="button"
          onClick={() => setExpanded(false)}
          aria-expanded={true}
          aria-label="Collapse AI status"
          className="rounded p-1 text-slate-400 transition hover:bg-slate-700 hover:text-slate-200"
        >
          <ChevronUp size={14} />
        </button>
      </div>

      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-500/20">
          <Zap size={14} className="text-brand-400" />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-white">
            Azure OpenAI
          </span>
          <span className="text-[11px] text-slate-400">
            {aiLabel ? aiLabel.text : status.text}
          </span>
        </div>
        <div className="ml-auto">
          <div className={`h-2 w-2 rounded-full ${status.dotColor}`} />
        </div>
      </div>

      <div className="space-y-2 border-t border-slate-700 pt-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database size={12} className="text-slate-400" />
            <span className="text-[12px] text-slate-400">RAG Index</span>
          </div>
          <span
            className={`text-[12px] font-medium ${searchLabel?.color ?? "text-slate-500"}`}
          >
            {searchLabel?.text ?? "Unknown"}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <RefreshCw size={12} className="text-slate-400" />
            <span className="text-[12px] text-slate-400">Last Check</span>
          </div>
          <span className="text-[12px] font-medium text-slate-300">
            {health?.checked_at ? formatTimeAgo(health.checked_at) : "—"}
          </span>
        </div>
      </div>
    </div>
  );
}
