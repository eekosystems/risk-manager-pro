import { useMemo, useState } from "react";
import { AlertTriangle, Clock, Loader2, Plus, ShieldAlert, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { RiskMatrix } from "@/components/ui/risk-matrix";
import { useDeleteRisk, useRisks } from "@/hooks/use-risks";
import type { RiskEntryListItem, RiskStatus } from "@/types/api";
import {
  LIKELIHOOD_LABELS,
  RISK_LEVEL_CONFIG,
  SEVERITY_LABELS,
  type Likelihood,
  type RiskLevel,
  type RiskMatrixSelection,
  type RiskPositionCount,
  type Severity,
} from "@/types/risk-matrix";

const STATUS_LABELS: Record<RiskStatus, { label: string; className: string }> = {
  open: { label: "Open", className: "text-brand-600 bg-brand-50" },
  mitigating: { label: "Mitigating", className: "text-accent-600 bg-accent-50" },
  closed: { label: "Closed", className: "text-brand-400 bg-brand-50" },
  accepted: { label: "Accepted", className: "text-brand-800 bg-brand-50" },
};

const ALL_AIRPORTS = "__all__";

interface RiskListViewProps {
  onSelectRisk: (riskId: string) => void;
  onCreateNew: () => void;
}

export function RiskListView({ onSelectRisk, onCreateNew }: RiskListViewProps) {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [riskLevelFilter, setRiskLevelFilter] = useState<string>("");
  const [airportFilter, setAirportFilter] = useState<string>(ALL_AIRPORTS);
  const [selectedCell, setSelectedCell] = useState<RiskMatrixSelection | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  // Single wide fetch — we filter client-side so the airport-pill bar stays
  // populated even when a specific airport is selected.
  const { data, isLoading } = useRisks({
    ...(statusFilter ? { status: statusFilter } : {}),
    ...(riskLevelFilter ? { risk_level: riskLevelFilter } : {}),
    limit: 500,
  });
  const deleteMutation = useDeleteRisk();

  const allRisks: RiskEntryListItem[] = data?.data ?? [];

  // Every airport that shows up in the fetched dataset — this powers the pill row.
  const airports: string[] = useMemo(() => {
    const s = new Set<string>();
    for (const r of allRisks) {
      if (r.airport_identifier) s.add(r.airport_identifier);
    }
    return [...s].sort();
  }, [allRisks]);

  // Apply the airport pill filter.
  const risks: RiskEntryListItem[] = useMemo(() => {
    if (airportFilter === ALL_AIRPORTS) return allRisks;
    return allRisks.filter((r) => r.airport_identifier === airportFilter);
  }, [allRisks, airportFilter]);

  // Apply the matrix-cell drill-down filter — final list shown in right panel.
  const cellRisks: RiskEntryListItem[] = useMemo(() => {
    if (!selectedCell) return [];
    return risks.filter(
      (r) =>
        (r.likelihood as Likelihood) === selectedCell.likelihood &&
        (r.severity as Severity) === selectedCell.severity,
    );
  }, [risks, selectedCell]);

  const total = risks.length;
  const openCount = risks.filter((r) => r.status === "open").length;
  const highCount = risks.filter(
    (r) => r.risk_level === "high" || r.risk_level === "extreme",
  ).length;

  const riskPositions: RiskPositionCount[] = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of risks) {
      const key = `${r.likelihood}-${r.severity}`;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return Array.from(counts.entries()).map(([key, count]) => {
      const [likelihood, severityStr] = key.split("-");
      return {
        likelihood: likelihood as Likelihood,
        severity: Number(severityStr) as Severity,
        count,
      };
    });
  }, [risks]);

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

  function handleCellSelect(sel: RiskMatrixSelection) {
    // Toggle: clicking the same cell clears the drill-down.
    if (
      selectedCell &&
      selectedCell.likelihood === sel.likelihood &&
      selectedCell.severity === sel.severity
    ) {
      setSelectedCell(null);
    } else {
      setSelectedCell(sel);
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
    <div className="mx-auto max-w-7xl p-6">
      {/* Airport pills */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          Airport:
        </span>
        <AirportPill
          label={`All (${allRisks.length})`}
          active={airportFilter === ALL_AIRPORTS}
          onClick={() => setAirportFilter(ALL_AIRPORTS)}
        />
        {airports.map((code) => {
          const count = allRisks.filter((r) => r.airport_identifier === code).length;
          return (
            <AirportPill
              key={code}
              label={`${code} (${count})`}
              active={airportFilter === code}
              onClick={() => setAirportFilter(code)}
            />
          );
        })}
        {airports.length === 0 && (
          <span className="text-[12px] italic text-slate-400">
            No airport identifiers on current records
          </span>
        )}
      </div>

      {/* Stats cards */}
      <div className="mb-6 grid grid-cols-3 gap-4">
        <div className="rounded-2xl border border-gray-200 bg-white p-4">
          <div className="text-2xl font-bold text-brand-500">{total}</div>
          <div className="text-[12px] text-slate-500">
            Total Risks
            {airportFilter !== ALL_AIRPORTS ? ` — ${airportFilter}` : ""}
          </div>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4">
          <div className="text-2xl font-bold text-brand-600">{openCount}</div>
          <div className="text-[12px] text-slate-500">Open</div>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4">
          <div className="text-2xl font-bold text-brand-600">{highCount}</div>
          <div className="text-[12px] text-slate-500">High / Extreme</div>
        </div>
      </div>

      {/* Risk Distribution + Drill-down panel */}
      {risks.length > 0 && (
        <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)]">
          <div className="rounded-2xl border border-gray-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-700">Risk Distribution</h3>
              <span className="text-[11px] text-slate-400">
                {selectedCell
                  ? "Click the cell again to clear drill-down"
                  : "Click any cell to drill in"}
              </span>
            </div>
            <RiskMatrix
              selection={selectedCell}
              onSelect={handleCellSelect}
              riskPositions={riskPositions}
            />
          </div>

          {selectedCell && (
            <CellDrillDown
              selection={selectedCell}
              risks={cellRisks}
              onSelectRisk={onSelectRisk}
              onClose={() => setSelectedCell(null)}
            />
          )}
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
          <option value="extreme">Extreme</option>
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
            description={
              airportFilter === ALL_AIRPORTS
                ? "Create your first risk entry to start tracking hazards and mitigations."
                : `No risk entries for ${airportFilter} yet. Switch airport or create a new entry.`
            }
            actionLabel="New Risk Entry"
            onAction={onCreateNew}
          />
        ) : (
          risks.map((risk, index) => {
            const levelCfg =
              RISK_LEVEL_CONFIG[risk.risk_level as RiskLevel] ?? RISK_LEVEL_CONFIG.low;
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
                    {risk.airport_identifier && (
                      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-mono font-bold text-slate-600">
                        {risk.airport_identifier}
                      </span>
                    )}
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${levelCfg.bg} ${levelCfg.color}`}
                    >
                      {levelCfg.label}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${statusCfg.className}`}
                    >
                      {statusCfg.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-[12px] text-slate-400">
                    <span className="truncate max-w-[300px]">{risk.hazard}</span>
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

// ---- Subcomponents ---------------------------------------------------------

function AirportPill({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-[12px] font-semibold transition-colors ${
        active
          ? "border-brand-500 bg-brand-500 text-white"
          : "border-gray-200 bg-white text-slate-600 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-600"
      }`}
    >
      {label}
    </button>
  );
}

function CellDrillDown({
  selection,
  risks,
  onSelectRisk,
  onClose,
}: {
  selection: RiskMatrixSelection;
  risks: RiskEntryListItem[];
  onSelectRisk: (riskId: string) => void;
  onClose: () => void;
}) {
  const levelCfg = RISK_LEVEL_CONFIG[selection.riskLevel];
  const severityCfg = SEVERITY_LABELS[selection.severity];
  const likelihoodCfg = LIKELIHOOD_LABELS[selection.likelihood];

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span
              className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${levelCfg.bg} ${levelCfg.color}`}
            >
              {levelCfg.label}
            </span>
            <h3 className="text-sm font-bold text-slate-700">
              {risks.length} {risks.length === 1 ? "risk" : "risks"}
            </h3>
          </div>
          <p className="mt-1 text-[12px] text-slate-500">
            Severity {severityCfg.short} ({severityCfg.full}) × Likelihood{" "}
            {selection.likelihood} ({likelihoodCfg.full})
          </p>
        </div>
        <button
          onClick={onClose}
          aria-label="Clear cell drill-down"
          className="rounded-lg p-1 text-slate-400 hover:bg-gray-100 hover:text-slate-600"
        >
          <X size={14} />
        </button>
      </div>

      {risks.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-200 p-6 text-center text-[12px] text-slate-400">
          No risks at this severity/likelihood coordinate for the current filter.
        </div>
      ) : (
        <div className="max-h-[420px] space-y-1 overflow-y-auto">
          {risks.map((risk) => (
            <button
              key={risk.id}
              onClick={() => onSelectRisk(risk.id)}
              className="flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left transition-colors hover:bg-gray-50"
            >
              <AlertTriangle
                size={14}
                className="mt-0.5 shrink-0 text-brand-500"
              />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="truncate text-[13px] font-semibold text-slate-800">
                    {risk.title}
                  </span>
                  {risk.airport_identifier && (
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-mono font-bold text-slate-600">
                      {risk.airport_identifier}
                    </span>
                  )}
                </div>
                <div className="truncate text-[11px] text-slate-500">
                  {risk.hazard}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
