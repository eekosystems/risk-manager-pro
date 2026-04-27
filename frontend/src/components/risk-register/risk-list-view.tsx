import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Clock,
  ExternalLink,
  Loader2,
  Plus,
  ShieldAlert,
  Trash2,
  X,
} from "lucide-react";

import {
  getRiskOutcomeSummary,
  type SharePointParseNote,
  type SharePointRiskRow,
} from "@/api/sharepoint";
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

/**
 * Adapt a SharePoint-extracted risk to the same shape `RiskEntryListItem`
 * uses so it can be rendered by the matrix + drill-down alongside DB risks.
 *
 * Synthetic fields we don't have from the PDF extraction:
 * - id: `sp:<file>:<hash>` so it's stable across renders and distinguishable
 *   from DB ids
 * - status: "open" (these are external observations, not tracked state)
 * - validation_status: "user_reported" to flag they weren't RMP-validated
 * - source: "fg_push" since they come from Faith Group's SharePoint
 */
function spToListItem(r: SharePointRiskRow, idx: number): RiskEntryListItem {
  return {
    id: `sp:${r.source_file}:${idx}`,
    title: r.hazard,
    hazard: r.hazard,
    severity: r.severity,
    likelihood: r.likelihood,
    risk_level: r.risk_level,
    status: "open",
    function_type: "risk_register",
    airport_identifier: r.airport_identifier,
    operational_domain: null,
    hazard_category_5m: null,
    record_status: "monitoring",
    validation_status: "user_reported",
    source: "fg_push",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

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

  // Pull the SharePoint risk-outcome scan — airport list + hazards extracted
  // from each airport's /risk-outcome/ PDFs via LLM. Poll while scanning so
  // the matrix + pills update live as more files are indexed. Also nudge
  // the backend to re-scan when the result shows zero risks (usually
  // signals a silent failure rather than a genuinely empty portfolio).
  const { data: spSummary } = useQuery({
    queryKey: ["sharepoint-risk-outcome-summary"],
    queryFn: () => getRiskOutcomeSummary(false),
    refetchInterval: (q) => {
      const d = q.state.data;
      if (!d) return false;
      if (d.status === "scanning") return 5000; // poll while in progress
      if (d.risks.length === 0 && d.airports.length > 0) return 15000; // retry empty results
      return 60000; // steady-state heartbeat every minute
    },
  });

  const dbRisks: RiskEntryListItem[] = useMemo(
    () => data?.data ?? [],
    [data?.data],
  );

  // Merge DB-backed risks with SharePoint-extracted risks into one list for
  // the 5x5 distribution + drill-down. Use a synthetic id so the drill-down
  // can still key rows (SP risks have no DB id). Dedup on (airport, hazard)
  // so a hazard that exists in both the DB and a SharePoint PDF only appears
  // once on the matrix — DB rows win because they're the validated/edited copy.
  const allRisks: RiskEntryListItem[] = useMemo(() => {
    const seen = new Set<string>();
    const merged: RiskEntryListItem[] = [];
    const keyFor = (r: RiskEntryListItem) =>
      `${r.airport_identifier ?? ""}::${(r.hazard ?? r.title ?? "").toLowerCase().trim().slice(0, 120)}`;
    for (const r of dbRisks) {
      const k = keyFor(r);
      if (seen.has(k)) continue;
      seen.add(k);
      merged.push(r);
    }
    for (const r of (spSummary?.risks ?? []).map(spToListItem)) {
      const k = keyFor(r);
      if (seen.has(k)) continue;
      seen.add(k);
      merged.push(r);
    }
    return merged;
  }, [dbRisks, spSummary?.risks]);

  // Side table: synthetic id → SharePoint URL, so clicking an SP-sourced
  // row opens the PDF in a new tab instead of hitting the detail endpoint
  // (which would 404 on the synthetic id).
  const spUrlById: Map<string, string> = useMemo(() => {
    const m = new Map<string, string>();
    (spSummary?.risks ?? []).forEach((r, idx) => {
      const id = `sp:${r.source_file}:${idx}`;
      if (r.source_url) m.set(id, r.source_url);
    });
    return m;
  }, [spSummary?.risks]);

  function handleSelectRisk(riskId: string) {
    if (riskId.startsWith("sp:")) {
      const url = spUrlById.get(riskId);
      if (url) window.open(url, "_blank", "noopener,noreferrer");
      return;
    }
    onSelectRisk(riskId);
  }

  // Every airport that shows up in the fetched dataset — this powers the pill row.
  // Union of (SharePoint folder list) + (airports present in DB or SP risks).
  const airports: string[] = useMemo(() => {
    const s = new Set<string>();
    for (const a of spSummary?.airports ?? []) s.add(a);
    for (const r of allRisks) {
      if (r.airport_identifier) s.add(r.airport_identifier);
    }
    return [...s].sort();
  }, [allRisks, spSummary?.airports]);

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
      {/* SharePoint scan status */}
      {spSummary && (
        <ScanStatusBanner
          status={spSummary.status}
          scanned={spSummary.scanned}
          total={spSummary.total}
          riskCount={spSummary.risks.length}
          airportCount={spSummary.airports.length}
          notes={spSummary.notes}
        />
      )}

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
              onSelectRisk={handleSelectRisk}
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
            const isSharePoint = risk.id.startsWith("sp:");
            return (
              <div
                key={risk.id}
                onClick={() => handleSelectRisk(risk.id)}
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
                    {isSharePoint ? (
                      <span className="flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                        <ExternalLink size={10} />
                        SharePoint
                      </span>
                    ) : (
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${statusCfg.className}`}
                      >
                        {statusCfg.label}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-[12px] text-slate-400">
                    <span className="truncate max-w-[300px]">{risk.hazard}</span>
                    {!isSharePoint && (
                      <span className="flex items-center gap-1">
                        <Clock size={10} />
                        {new Date(risk.updated_at).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </span>
                    )}
                  </div>
                </div>
                {!isSharePoint && (
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
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

// ---- Subcomponents ---------------------------------------------------------

function ScanStatusBanner({
  status,
  scanned,
  total,
  riskCount,
  airportCount,
  notes,
}: {
  status: string;
  scanned: number;
  total: number;
  riskCount: number;
  airportCount: number;
  notes: SharePointParseNote[];
}) {
  const scanning = status === "scanning";
  const noteCount = notes.length;
  const [showNotes, setShowNotes] = useState(false);

  // Group repeated note messages so a common failure across many files
  // collapses to "<message> (43x)" instead of scrolling a wall of text.
  const groupedNotes = useMemo(() => {
    const m = new Map<string, { message: string; count: number; first: SharePointParseNote }>();
    for (const n of notes) {
      const key = n.message;
      const entry = m.get(key);
      if (entry) {
        entry.count += 1;
      } else {
        m.set(key, { message: key, count: 1, first: n });
      }
    }
    return Array.from(m.values()).sort((a, b) => b.count - a.count);
  }, [notes]);

  return (
    <div
      className={`mb-3 rounded-xl border px-3 py-2 text-[12px] ${
        scanning
          ? "border-brand-200 bg-brand-50 text-brand-700"
          : "border-gray-200 bg-gray-50 text-slate-600"
      }`}
    >
      <div className="flex items-center gap-2">
        {scanning ? (
          <Loader2 size={14} className="animate-spin" />
        ) : (
          <ShieldAlert size={14} />
        )}
        <span>
          {scanning
            ? `Extracting risks from SharePoint PDFs — ${scanned}/${total} files`
            : `SharePoint: ${riskCount} risks across ${airportCount} airports`}
          {noteCount > 0 && (
            <button
              onClick={() => setShowNotes((v) => !v)}
              className="ml-2 underline decoration-dotted text-slate-500 hover:text-slate-700"
            >
              ({noteCount} {showNotes ? "▼" : "▸"} issues)
            </button>
          )}
        </span>
      </div>
      {showNotes && noteCount > 0 && (
        <div className="mt-2 max-h-48 overflow-y-auto rounded-lg border border-gray-200 bg-white p-2 text-[11px]">
          {groupedNotes.map((g) => (
            <div key={g.message} className="border-b border-gray-100 py-1 last:border-0">
              <span className="font-semibold text-slate-700">
                {g.count > 1 ? `${g.count}× ` : ""}
              </span>
              <span className="text-slate-600">{g.message}</span>
              {g.count === 1 && (g.first.airport_identifier || g.first.source_file) && (
                <span className="ml-2 text-slate-400">
                  — {g.first.airport_identifier} / {g.first.source_file}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

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
