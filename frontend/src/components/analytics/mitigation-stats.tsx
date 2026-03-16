import { CheckCircle2, Clock, Target } from "lucide-react";

import type { MitigationPerformance } from "@/types/api";

interface MitigationStatsProps {
  data: MitigationPerformance;
}

export function MitigationStats({ data }: MitigationStatsProps) {
  const pct = Math.round(data.completion_rate * 100);

  return (
    <div className="space-y-3">
      {/* Completion rate */}
      <div className="rounded-xl border border-gray-200 bg-white p-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Target size={14} className="text-brand-500" />
            <span className="text-xs font-medium text-slate-600">Completion Rate</span>
          </div>
          <span className="text-lg font-bold text-brand-500">{pct}%</span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-gray-100">
          <div
            className="h-full rounded-full bg-brand-500 transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="mt-1.5 text-[10px] text-slate-400">
          {data.completed_count} of {data.total_mitigations} completed
        </div>
      </div>

      {/* Overdue */}
      <div className="rounded-xl border border-gray-200 bg-white p-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock size={14} className="text-amber-500" />
            <span className="text-xs font-medium text-slate-600">Overdue</span>
          </div>
          <span className={`text-lg font-bold ${data.overdue_count > 0 ? "text-amber-500" : "text-green-500"}`}>
            {data.overdue_count}
          </span>
        </div>
      </div>

      {/* Avg days */}
      <div className="rounded-xl border border-gray-200 bg-white p-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} className="text-green-500" />
            <span className="text-xs font-medium text-slate-600">Avg Days to Complete</span>
          </div>
          <span className="text-lg font-bold text-slate-700">
            {data.avg_days_to_complete != null ? `${data.avg_days_to_complete}d` : "--"}
          </span>
        </div>
      </div>
    </div>
  );
}
