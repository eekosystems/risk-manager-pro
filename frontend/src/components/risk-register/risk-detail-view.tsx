import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, Edit3, Loader2, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { requestClosureApproval } from "@/api/rr-sync";
import { Button } from "@/components/ui/button";
import { RiskMatrix } from "@/components/ui/risk-matrix";
import { useRisk } from "@/hooks/use-risks";
import { useToast } from "@/hooks/use-toast";
import type {
  HazardCategory5M,
  HazardCategoryICAO,
  OperationalDomain,
  RecordSource,
  RecordStatus,
  RiskStatus,
  ValidationStatus,
} from "@/types/api";
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
  open: { label: "Open", className: "text-brand-600 bg-brand-50" },
  mitigating: { label: "Mitigating", className: "text-accent-600 bg-accent-50" },
  closed: { label: "Closed", className: "text-brand-400 bg-brand-50" },
  accepted: { label: "Accepted", className: "text-brand-800 bg-brand-50" },
};

const DOMAIN_LABELS: Record<OperationalDomain, string> = {
  movement_area: "Movement Area",
  non_movement_area: "Non-Movement Area",
  ramp: "Ramp / Apron",
  terminal: "Terminal",
  landside: "Landside",
  user_defined: "User-defined",
};

const CATEGORY_5M_LABELS: Record<HazardCategory5M, string> = {
  human: "Human",
  machine: "Machine",
  medium: "Medium",
  mission: "Mission",
  management: "Management",
};

const CATEGORY_ICAO_LABELS: Record<HazardCategoryICAO, string> = {
  technical: "Technical",
  human: "Human",
  organizational: "Organizational",
  environmental: "Environmental",
};

const RECORD_STATUS_LABELS: Record<RecordStatus, string> = {
  open: "Open",
  in_progress: "In Progress",
  pending_assessment: "Pending Assessment",
  closed: "Closed",
  monitoring: "Monitoring",
};

const VALIDATION_LABELS: Record<ValidationStatus, { label: string; className: string }> = {
  rmp_validated: { label: "RMP-Validated", className: "bg-green-50 text-green-700" },
  user_reported: { label: "User-Reported", className: "bg-amber-50 text-amber-700" },
  pending: { label: "Pending", className: "bg-gray-100 text-gray-600" },
};

const SOURCE_LABELS: Record<RecordSource, string> = {
  rmp_sp1: "RMP — System Analysis (SP1)",
  rmp_sp2: "RMP — PHL (SP2)",
  rmp_sp3: "RMP — SRA (SP3)",
  rmp_sp4: "RMP — Risk Register Chat (SP4)",
  manual_entry: "Manual Entry",
  fg_push: "FG Push",
  client_push: "Client Push",
};

interface RiskDetailViewProps {
  riskId: string;
  onBack: () => void;
  onEdit: () => void;
}

export function RiskDetailView({ riskId, onBack, onEdit }: RiskDetailViewProps) {
  const { data: risk, isLoading } = useRisk(riskId);
  const { addToast } = useToast();
  const [closureNote, setClosureNote] = useState("");
  const [showClosureForm, setShowClosureForm] = useState(false);
  const closureMut = useMutation({
    mutationFn: (note: string) => requestClosureApproval(riskId, note),
    onSuccess: () => {
      addToast(
        "Closure approval requested. The Accountable Executive must review before this record can be closed.",
        "success",
      );
      setShowClosureForm(false);
      setClosureNote("");
    },
    onError: (err: Error) =>
      addToast(`Closure request failed: ${err.message}`, "error"),
  });

  if (isLoading || !risk) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={24} className="animate-spin text-brand-500" />
      </div>
    );
  }

  const requiresAEApproval =
    risk.risk_level === "high" || risk.risk_level === "extreme";

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
        <div className="flex items-center gap-2">
          {requiresAEApproval && (
            <Button
              variant="secondary"
              onClick={() => setShowClosureForm((v) => !v)}
            >
              <ShieldCheck size={14} className="mr-2" />
              Request AE Closure
            </Button>
          )}
          <Button variant="secondary" onClick={onEdit}>
            <Edit3 size={14} className="mr-2" />
            Edit
          </Button>
        </div>
      </div>

      {showClosureForm && requiresAEApproval && (
        <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <div className="mb-2 text-sm font-semibold text-amber-900">
            Request Accountable Executive approval
          </div>
          <p className="mb-3 text-[12px] text-amber-800">
            High and Extreme records cannot be closed without AE sign-off. Submit
            this request and an approver with the Accountable Executive role will
            review.
          </p>
          <textarea
            value={closureNote}
            onChange={(e) => setClosureNote(e.target.value)}
            rows={3}
            placeholder="Optional note explaining why this record should be closed"
            className="mb-2 w-full rounded-lg border border-amber-200 bg-white px-3 py-2 text-sm focus:border-amber-400 focus:outline-none"
          />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowClosureForm(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => closureMut.mutate(closureNote)}
              disabled={closureMut.isPending}
            >
              {closureMut.isPending ? "Submitting…" : "Submit request"}
            </Button>
          </div>
        </div>
      )}

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
              {SEVERITY_LABELS[risk.severity as Severity]?.full ?? risk.severity} ({SEVERITY_LABELS[risk.severity as Severity]?.short ?? risk.severity})
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

        {/* Sub-Prompt 4 / Risk Register fields */}
        {(risk.airport_identifier ||
          risk.operational_domain ||
          risk.sub_location ||
          risk.hazard_category_5m ||
          risk.hazard_category_icao ||
          risk.validation_status !== "pending" ||
          risk.source !== "manual_entry") && (
          <div className="mt-5 grid grid-cols-2 gap-4 border-t border-gray-100 pt-5 md:grid-cols-3">
            {risk.airport_identifier && (
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
                  Airport
                </div>
                <div className="mt-1 text-sm font-mono text-slate-700">
                  {risk.airport_identifier}
                </div>
              </div>
            )}
            {risk.operational_domain && (
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
                  Operational Domain
                </div>
                <div className="mt-1 text-sm text-slate-700">
                  {DOMAIN_LABELS[risk.operational_domain]}
                </div>
              </div>
            )}
            {risk.sub_location && (
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
                  Sub-Location
                </div>
                <div className="mt-1 text-sm text-slate-700">{risk.sub_location}</div>
              </div>
            )}
            {risk.hazard_category_5m && (
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
                  5M (Primary)
                </div>
                <div className="mt-1 text-sm text-slate-700">
                  {CATEGORY_5M_LABELS[risk.hazard_category_5m]}
                </div>
              </div>
            )}
            {risk.hazard_category_icao && (
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
                  ICAO (Secondary)
                </div>
                <div className="mt-1 text-sm text-slate-700">
                  {CATEGORY_ICAO_LABELS[risk.hazard_category_icao]}
                </div>
              </div>
            )}
            {risk.residual_risk_level && (
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
                  Residual Risk
                </div>
                <div className="mt-1 text-sm font-semibold capitalize text-slate-700">
                  {risk.residual_risk_level}
                </div>
              </div>
            )}
            <div>
              <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
                Record Status
              </div>
              <div className="mt-1 text-sm text-slate-700">
                {RECORD_STATUS_LABELS[risk.record_status]}
              </div>
            </div>
            <div>
              <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
                Validation
              </div>
              <div className="mt-1">
                <span
                  className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${VALIDATION_LABELS[risk.validation_status].className}`}
                >
                  {VALIDATION_LABELS[risk.validation_status].label}
                </span>
              </div>
            </div>
            <div>
              <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
                Source
              </div>
              <div className="mt-1 text-sm text-slate-700">
                {SOURCE_LABELS[risk.source]}
              </div>
            </div>
          </div>
        )}

        {risk.potential_credible_outcome && (
          <div className="mt-4 border-t border-gray-100 pt-4">
            <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
              Worst Credible Outcome
            </div>
            <p className="mt-1 text-sm text-slate-600">
              {risk.potential_credible_outcome}
            </p>
          </div>
        )}

        {risk.existing_controls && (
          <div className="mt-4 border-t border-gray-100 pt-4">
            <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
              Existing Controls
            </div>
            <p className="mt-1 text-sm text-slate-600">{risk.existing_controls}</p>
          </div>
        )}

        {risk.acm_cross_reference && (
          <div className="mt-4 border-t border-gray-100 pt-4">
            <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
              ACM Cross-Reference
            </div>
            <p className="mt-1 text-sm text-slate-600">{risk.acm_cross_reference}</p>
          </div>
        )}

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
