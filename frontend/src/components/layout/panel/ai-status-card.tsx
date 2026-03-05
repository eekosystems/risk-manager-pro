import { useQuery } from "@tanstack/react-query";
import { Database, RefreshCw, Zap } from "lucide-react";

import { getHealthStatus, type HealthStatus } from "@/api/health";

export function AiStatusCard() {
  const { data: health } = useQuery<HealthStatus>({
    queryKey: ["health"],
    queryFn: getHealthStatus,
    refetchInterval: 30_000,
  });

  const isOnline = health?.status === "healthy";

  return (
    <div className="rounded-xl bg-slate-800 p-4" role="status">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
          AI Status
        </span>
      </div>

      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-500/20">
          <Zap size={14} className="text-brand-400" />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-white">Claude Opus</span>
          <span className="text-[11px] text-slate-400">
            {isOnline ? "Connected" : health ? "Degraded" : "Checking..."}
          </span>
        </div>
        <div className="ml-auto">
          <div
            className={`h-2 w-2 rounded-full ${isOnline ? "bg-green-400" : "bg-yellow-400"}`}
          />
        </div>
      </div>

      <div className="space-y-2 border-t border-slate-700 pt-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database size={12} className="text-slate-400" />
            <span className="text-[12px] text-slate-400">RAG Index</span>
          </div>
          <span className="text-[12px] font-medium text-green-400">Active</span>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <RefreshCw size={12} className="text-slate-400" />
            <span className="text-[12px] text-slate-400">Last Sync</span>
          </div>
          <span className="text-[12px] font-medium text-slate-300">2 min ago</span>
        </div>
      </div>
    </div>
  );
}
