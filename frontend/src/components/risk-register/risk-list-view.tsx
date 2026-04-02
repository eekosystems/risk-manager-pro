import { useState } from "react";
import {
  AlertTriangle,
  Clock,
  Loader2,
  Plus,
  ShieldAlert,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { RiskMatrix } from "@/components/ui/risk-matrix";
import { useDeleteRisk, useRisks } from "@/hooks/use-risks";
import type { RiskEntryListItem, RiskStatus } from "@/types/api";
import {
  RISK_LEVEL_CONFIG,
  type Likelihood,
  type RiskLevel,
  type RiskPositionCount,
  type Severity,
} from "@/types/risk-matrix";

const STATUS_LABELS: Record<RiskStatus, { label: string; className: string }> = {
  open: { label: "Open", className: "text-blue-600 bg-blue-50" },
  mitigating: { label: "Mitigating", className: "text-amber-600 bg-amber-50" },
  closed: { label: "Closed", className: "text-green-600 bg-green-50" },
  accepted: { label: "Accepted", className: "text-purple-600 bg-purple-50" },
};

interface RiskListViewProps {
  onSelectRisk: (riskId: string) => void;
  onCreateNew: () => void;
}

export function RiskListView({ onSelectRisk, onCreateNew }: RiskListViewProps) {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [riskLevelFilter, setRiskLevelFilter] = useState<string>("");
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const { data, isLoading } = useRisks({
    ...(statusFilter ? { status: statusFilter } : {}),
    ...(riskLevelFilter ? { risk_level: riskLevelFilter } : {}),
    limit: 100,
  });
  const deleteMutation = useDeleteRisk();

  const risks = data?.data ?? [];
  const total = data?.total ?? 0;

  const openCount = risks.filter((r) => r.status === "open").length;
  const highCount = risks.filter(
    (r) => r.risk_level === "high",
  ).length;

  const riskPositions: RiskPositionCount[] = (() => {
    const counts = new Map<string, number>();
    for (const risk of risks) {
      const key = `${risk.likelihood}-${risk.severity}`;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    const result: RiskPositionCount[] = [];
    for (const [key, count] of counts) {
      const [likelihood, severityStr] = key.split("-");
      result.push({
        likelihood: likelihood as Likelihood,
        severity: Number(severityStr) as Severity,
        count,
      });
    }
    return result;
  })();

  function handleDelete(e: React.MouseEvent, riskId: string) {
    e.stopPropagation();
    if (deleteConfirm === riskId) {
      deleteMutation.mutate(riskId);
      setDeleteConfirm(null);
    } else {
      setDeleteConfirm(riskId);
      setTimeout(() => setDeleteConfirm(null), 3000);
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={24} className="animate-spin text-brand-500" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      {/* Stats cards */}
      <div className="mb-6 grid grid-cols-3 gap-4">
        <div className="rounded-2xl border border-gray-200 bg-white p-4">
          <div className="text-2xl font-bold text-brand-500">{total}</div>
          <div className="text-[12px] text-slate-500">Total Risks</div>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4">
          <div className="text-2xl font-bold text-blue-500">{openCount}</div>
          <div className="text-[12px] text-slate-500">Open</div>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4">
          <div className="text-2xl font-bold text-red-500">{highCount}</div>
          <div className="text-[12px] text-slate-500">High</div>
        </div>
      </div>

      {/* Risk Matrix Heatmap */}
      {risks.length > 0 && (
        <div className="mb-6 rounded-2xl border border-gray-200 bg-white p-4">
          <h3 className="mb-3 text-sm font-bold text-slate-700">Risk Distribution</h3>
          <RiskMatrix
            selection={null}
            onSelect={() => {}}
            riskPositions={riskPositions}
            readOnly
          />
        </div>
      )}

      {/* Actions + Filters */}
      <div className="mb-4 flex items-center gap-3">
        <Button onClick={onCreateNew}>
          <Plus size={16} className="mr-2" />
          New Risk Entry
        </Button>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
        >
          <option value="">All Statuses</option>
          <option value="open">Open</option>
          <option value="mitigating">Mitigating</option>
          <option value="closed">Closed</option>
          <option value="accepted">Accepted</option>
        </select>
        <select
          value={riskLevelFilter}
          onChange={(e) => setRiskLevelFilter(e.target.value)}
          className="rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
        >
          <option value="">All Risk Levels</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {/* Risk table */}
      <div className="rounded-2xl border border-gray-200 bg-white">
        {risks.length === 0 ? (
          <EmptyState
            icon={ShieldAlert}
            title="No risk entries"
            description="Create your first risk entry to start tracking hazards and mitigations."
            actionLabel="New Risk Entry"
            onAction={onCreateNew}
          />
        ) : (
          risks.map((risk: RiskEntryListItem, index: number) => {
            const riskLevelCfg =
              RISK_LEVEL_CONFIG[risk.risk_level as RiskLevel] ??
              RISK_LEVEL_CONFIG.low;
            const statusCfg = STATUS_LABELS[risk.status] ?? STATUS_LABELS.open;
            return (
              <div
                key={risk.id}
                onClick={() => onSelectRisk(risk.id)}
                className={`flex cursor-pointer items-center gap-4 px-5 py-4 transition-colors hover:bg-gray-50 ${
                  index < risks.length - 1 ? "border-b border-gray-100" : ""
                }`}
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50">
                  <AlertTriangle size={18} className="text-brand-500" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-semibold text-slate-800">
                      {risk.title}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${riskLevelCfg.bg} ${riskLevelCfg.color}`}
                    >
                      {riskLevelCfg.label}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${statusCfg.className}`}
                    >
                      {statusCfg.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-[12px] text-slate-400">
                    <span className="truncate max-w-[300px]">
                      {risk.hazard}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock size={10} />
                      {new Date(risk.updated_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </span>
                  </div>
                </div>
                <button
                  onClick={(e) => handleDelete(e, risk.id)}
                  disabled={deleteMutation.isPending}
                  className={`rounded-lg p-2 transition-colors ${
                    deleteConfirm === risk.id
                      ? "bg-red-50 text-red-500 hover:bg-red-100"
                      : "text-gray-300 hover:bg-red-50 hover:text-red-500"
                  }`}
                  title={
                    deleteConfirm === risk.id
                      ? "Click again to confirm delete"
                      : "Delete risk"
                  }
                >
                  <Trash2 size={16} />
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
