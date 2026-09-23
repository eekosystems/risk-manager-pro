import { Loader2, RefreshCw } from "lucide-react";

import {
  useConfirmResidualAssessment,
  useDismissResidualAssessment,
  useRequestResidualAssessment,
} from "@/hooks/use-risks";
import { useToast } from "@/hooks/use-toast";
import type { ResidualAssessment, RiskEntryListItem } from "@/types/api";

import { RiskCellBadge } from "./risk-cell-badge";

const FAILURE_MESSAGES: Record<string, string> = {
  INSUFFICIENT_BASIS:
    "The SRA engine could not support a residual from the recorded mitigations and indexed documents.",
  INVALID_RESULT: "The SRA engine returned an incomplete assessment.",
  LLM_ERROR: "The SRA engine could not be reached.",
};

interface ResidualRiskCellProps {
  risk: RiskEntryListItem;
  canEdit: boolean;
  /** SharePoint rows not yet imported have no record to re-assess. */
  isImported: boolean;
}

export function ResidualRiskCell({
  risk,
  canEdit,
  isImported,
}: ResidualRiskCellProps) {
  const assessment = risk.latest_assessment;
  return (
    <div className="space-y-1.5" onClick={(e) => e.stopPropagation()}>
      <RiskCellBadge
        likelihood={risk.residual_likelihood}
        severity={risk.residual_severity}
        level={risk.residual_risk_level}
      />
      {isImported && assessment?.status === "pending" && (
        <span className="flex items-center gap-1 text-[11px] text-brand-600">
          <Loader2 size={11} className="animate-spin" />
          Re-assessing…
        </span>
      )}
      {isImported && assessment?.status === "proposed" && (
        <ProposedResidual
          riskId={risk.id}
          assessment={assessment}
          canEdit={canEdit}
        />
      )}
      {isImported && assessment?.status === "failed" && (
        <FailedReassessment
          riskId={risk.id}
          assessment={assessment}
          canEdit={canEdit}
        />
      )}
    </div>
  );
}

function ProposedResidual({
  riskId,
  assessment,
  canEdit,
}: {
  riskId: string;
  assessment: ResidualAssessment;
  canEdit: boolean;
}) {
  const { addToast } = useToast();
  const confirm = useConfirmResidualAssessment(riskId);
  const dismiss = useDismissResidualAssessment(riskId);
  const busy = confirm.isPending || dismiss.isPending;

  return (
    <div
      className="rounded-lg border border-dashed border-brand-300 bg-brand-50/60 p-1.5"
      title={
        assessment.result
          ? `${assessment.result.alarp_status}\n\n${assessment.result.rationale}`
          : undefined
      }
    >
      <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-brand-700">
        Proposed
        <RiskCellBadge
          likelihood={assessment.residual_likelihood}
          severity={assessment.residual_severity}
          level={assessment.residual_risk_level}
        />
      </div>
      {canEdit && (
        <div className="flex gap-1">
          <button
            disabled={busy}
            onClick={() =>
              confirm.mutate(assessment.id, {
                onError: () =>
                  addToast("Could not confirm the residual risk", "error"),
              })
            }
            className="rounded-md bg-brand-500 px-2 py-0.5 text-[11px] font-semibold text-white hover:bg-brand-600 disabled:opacity-50"
          >
            Confirm
          </button>
          <button
            disabled={busy}
            onClick={() =>
              dismiss.mutate(assessment.id, {
                onError: () =>
                  addToast("Could not dismiss the proposal", "error"),
              })
            }
            className="rounded-md px-2 py-0.5 text-[11px] font-semibold text-slate-500 hover:bg-gray-100 disabled:opacity-50"
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}

function FailedReassessment({
  riskId,
  assessment,
  canEdit,
}: {
  riskId: string;
  assessment: ResidualAssessment;
  canEdit: boolean;
}) {
  const { addToast } = useToast();
  const retry = useRequestResidualAssessment(riskId);
  const dismiss = useDismissResidualAssessment(riskId);
  const message =
    FAILURE_MESSAGES[assessment.error_code ?? ""] ??
    "The re-assessment did not complete.";

  return (
    <div className="rounded-lg bg-amber-50 p-1.5 text-[11px] text-amber-800">
      <p>{message}</p>
      {canEdit && (
        <div className="mt-1 flex gap-1">
          <button
            disabled={retry.isPending}
            onClick={() =>
              retry.mutate(undefined, {
                onError: () =>
                  addToast("Could not start the re-assessment", "error"),
              })
            }
            className="flex items-center gap-1 rounded-md px-1.5 py-0.5 font-semibold hover:bg-amber-100 disabled:opacity-50"
          >
            <RefreshCw size={10} />
            Retry
          </button>
          <button
            disabled={dismiss.isPending}
            onClick={() =>
              dismiss.mutate(assessment.id, {
                onError: () =>
                  addToast("Could not dismiss the failed run", "error"),
              })
            }
            className="rounded-md px-1.5 py-0.5 font-semibold hover:bg-amber-100 disabled:opacity-50"
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}
