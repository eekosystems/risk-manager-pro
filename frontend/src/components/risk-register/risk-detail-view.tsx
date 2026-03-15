import { ArrowLeft, Edit3, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { RiskMatrix } from "@/components/ui/risk-matrix";
import { useRisk } from "@/hooks/use-risks";
import type { RiskStatus } from "@/types/api";
import {
  LIKELIHOOD_LABELS,
  RISK_LEVEL_CONFIG,
  SEVERITY_LABELS,
  type Likelihood,
  type RiskLevel,
  type RiskMatrixSelection,
  type Severity,
} from "@/types/risk-matrix";

import { MitigationList } from "./mitigation-list";

const STATUS_LABELS: Record<RiskStatus, { label: string; className: string }> = {
  open: { label: "Open", className: "text-blue-600 bg-blue-50" },
  mitigating: { label: "Mitigating", className: "text-amber-600 bg-amber-50" },
  closed: { label: "Closed", className: "text-green-600 bg-green-50" },
  accepted: { label: "Accepted", className: "text-purple-600 bg-purple-50" },
};

interface RiskDetailViewProps {
  riskId: string;
  onBack: () => void;
  onEdit: () => void;
}

export function RiskDetailView({ riskId, onBack, onEdit }: RiskDetailViewProps) {
  const { data: risk, isLoading } = useRisk(riskId);

  if (isLoading || !risk) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={24} className="animate-spin text-brand-500" />
      </div>
    );
  }

  const riskLevelCfg =
    RISK_LEVEL_CONFIG[risk.risk_level as RiskLevel] ?? RISK_LEVEL_CONFIG.low;
  const statusCfg = STATUS_LABELS[risk.status] ?? STATUS_LABELS.open;

  const matrixSelection: RiskMatrixSelection = {
    severity: risk.severity as Severity,
    likelihood: risk.likelihood as Likelihood,
    riskLevel: risk.risk_level as RiskLevel,
  };

  return (
    <div className="mx-auto max-w-5xl p-6">
      {/* Back + actions */}
      <div className="mb-6 flex items-center justify-between">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-sm font-medium text-slate-500 transition-colors hover:text-brand-500"
        >
          <ArrowLeft size={16} />
          Back to Risk Register
        </button>
        <Button variant="secondary" onClick={onEdit}>
          <Edit3 size={14} className="mr-2" />
          Edit
        </Button>
      </div>

      {/* Header card */}
      <div className="mb-6 rounded-2xl border border-gray-200 bg-white p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-slate-900">{risk.title}</h2>
              <span
                className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold ${riskLevelCfg.bg} ${riskLevelCfg.color}`}
              >
                {riskLevelCfg.label}
              </span>
              <span
                className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold ${statusCfg.className}`}
              >
                {statusCfg.label}
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-600">{risk.description}</p>
          </div>
        </div>

        {/* Info grid */}
        <div className="mt-5 grid grid-cols-2 gap-4 border-t border-gray-100 pt-5 md:grid-cols-4">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
              Hazard
            </div>
            <div className="mt-1 text-sm text-slate-700">{risk.hazard}</div>
          </div>
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
              Severity
            </div>
            <div className="mt-1 text-sm text-slate-700">
              {SEVERITY_LABELS[risk.severity as Severity]?.full ?? risk.severity} ({risk.severity})
            </div>
          </div>
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
              Likelihood
            </div>
            <div className="mt-1 text-sm text-slate-700">
              {LIKELIHOOD_LABELS[risk.likelihood as Likelihood]?.full ?? risk.likelihood} ({risk.likelihood})
            </div>
          </div>
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
              Function Type
            </div>
            <div className="mt-1 text-sm uppercase text-slate-700">
              {risk.function_type}
            </div>
          </div>
        </div>

        {risk.notes && (
          <div className="mt-4 border-t border-gray-100 pt-4">
            <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
              Notes
            </div>
            <p className="mt-1 text-sm text-slate-600">{risk.notes}</p>
          </div>
        )}

        <div className="mt-4 flex items-center gap-4 text-[11px] text-slate-400">
          <span>
            Created: {new Date(risk.created_at).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
          </span>
          <span>
            Updated: {new Date(risk.updated_at).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
          </span>
        </div>
      </div>

      {/* Risk Matrix (read-only display) */}
      <div className="mb-6 rounded-2xl border border-gray-200 bg-white p-6">
        <h3 className="mb-4 text-sm font-bold text-slate-900">Risk Matrix</h3>
        <RiskMatrix
          selection={matrixSelection}
          onSelect={() => {
            /* read-only in detail view */
          }}
        />
      </div>

      {/* Mitigations */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6">
        <MitigationList riskId={riskId} mitigations={risk.mitigations} />
      </div>
    </div>
  );
}
