import { BarChart3, Loader2 } from "lucide-react";

import { RiskMatrix } from "@/components/ui/risk-matrix";
import { useDashboard } from "@/hooks/use-analytics";
import type { Likelihood, RiskPositionCount, Severity } from "@/types/risk-matrix";

import { ActivityFeed } from "./activity-feed";
import { FunctionTypeChart } from "./function-type-chart";
import { KPICards } from "./kpi-cards";
import { MitigationStats } from "./mitigation-stats";
import { RiskTrendChart } from "./risk-trend-chart";
import { StatusDonutChart } from "./status-donut-chart";

export function AnalyticsDashboard() {
  const { data, isLoading } = useDashboard();

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 size={24} className="animate-spin text-brand-500" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-gray-400">
        Failed to load dashboard data
      </div>
    );
  }

  const riskPositions: RiskPositionCount[] = data.risk_positions.map((p) => ({
    likelihood: p.likelihood as Likelihood,
    severity: p.severity as Severity,
    count: p.count,
  }));

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-6xl space-y-6 p-6">
        {/* Row 1: KPI Cards */}
        <KPICards kpis={data.kpis} />

        {/* Row 2: Trend chart + Status donut */}
        <div className="grid grid-cols-5 gap-4">
          <div className="col-span-3 rounded-2xl border border-gray-200 bg-white p-5">
            <h3 className="mb-4 flex items-center gap-2 text-sm font-bold text-slate-700">
              <BarChart3 size={16} className="text-brand-500" />
              Risk Level Trend
            </h3>
            <RiskTrendChart data={data.risk_level_over_time} />
          </div>
          <div className="col-span-2 rounded-2xl border border-gray-200 bg-white p-5">
            <h3 className="mb-4 text-sm font-bold text-slate-700">
              Status Breakdown
            </h3>
            <StatusDonutChart data={data.status_breakdown} />
          </div>
        </div>

        {/* Row 3: Function type chart + Mitigation stats + Risk matrix */}
        <div className="grid grid-cols-5 gap-4">
          <div className="col-span-2 rounded-2xl border border-gray-200 bg-white p-5">
            <h3 className="mb-4 text-sm font-bold text-slate-700">
              Risks by Function Type
            </h3>
            <FunctionTypeChart data={data.by_function_type} />
          </div>
          <div className="col-span-1 rounded-2xl border border-gray-200 bg-white p-5">
            <h3 className="mb-4 text-sm font-bold text-slate-700">
              Mitigation Performance
            </h3>
            <MitigationStats data={data.mitigation_performance} />
          </div>
          <div className="col-span-2 rounded-2xl border border-gray-200 bg-white p-5">
            <h3 className="mb-3 text-sm font-bold text-slate-700">
              Risk Distribution
            </h3>
            <RiskMatrix
              selection={null}
              onSelect={() => {}}
              riskPositions={riskPositions}
              readOnly
            />
          </div>
        </div>

        {/* Row 4: Activity feed */}
        <div className="rounded-2xl border border-gray-200 bg-white p-5">
          <h3 className="mb-3 text-sm font-bold text-slate-700">
            Recent Activity
          </h3>
          <ActivityFeed />
        </div>
      </div>
    </div>
  );
}
