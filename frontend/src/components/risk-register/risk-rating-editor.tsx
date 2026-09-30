import { useState } from "react";
import { Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useUpdateRisk } from "@/hooks/use-risks";
import { useToast } from "@/hooks/use-toast";
import type { RiskEntryListItem, UpdateRiskEntryRequest } from "@/types/api";
import {
  LIKELIHOOD_LABELS,
  LIKELIHOODS,
  RISK_MATRIX,
  SEVERITIES,
  SEVERITY_LABELS,
  type RiskLevel,
} from "@/types/risk-matrix";

import { RiskCellBadge } from "./risk-cell-badge";

const SELECT_CLASS =
  "rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-[13px] text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

interface MatrixCell {
  likelihood: string | null;
  severity: number | null;
}

function levelFor(cell: MatrixCell): RiskLevel | null {
  if (cell.likelihood === null || cell.severity === null) return null;
  const row = (RISK_MATRIX as Record<string, Record<number, RiskLevel> | undefined>)[
    cell.likelihood
  ];
  return row?.[cell.severity] ?? null;
}

function sameCell(a: MatrixCell, b: MatrixCell): boolean {
  return a.likelihood === b.likelihood && a.severity === b.severity;
}

interface RiskRatingEditorProps {
  risk: RiskEntryListItem;
}

/** Edits a hazard's initial and residual cells on the FG 5x5 from the register row. */
export function RiskRatingEditor({ risk }: RiskRatingEditorProps) {
  const savedInitial: MatrixCell = {
    likelihood: risk.likelihood,
    severity: risk.severity,
  };
  const savedResidual: MatrixCell = {
    likelihood: risk.residual_likelihood,
    severity: risk.residual_severity,
  };
  const [initial, setInitial] = useState<MatrixCell>(savedInitial);
  const [residual, setResidual] = useState<MatrixCell>(savedResidual);
  const { addToast } = useToast();
  const update = useUpdateRisk();

  const initialChanged = !sameCell(initial, savedInitial);
  const residualChanged = !sameCell(residual, savedResidual);
  // A residual is a whole cell or not recorded at all.
  const residualHalfSet =
    (residual.likelihood === null) !== (residual.severity === null);
  const canSave =
    (initialChanged || residualChanged) && !residualHalfSet && !update.isPending;

  function handleSave() {
    const payload: UpdateRiskEntryRequest = {};
    if (initialChanged) {
      payload.likelihood = initial.likelihood;
      payload.severity = initial.severity;
    }
    if (residualChanged) {
      payload.residual_likelihood = residual.likelihood;
      payload.residual_severity = residual.severity;
    }
    update.mutate(
      { riskId: risk.id, payload },
      { onError: () => addToast("Could not save the risk rating", "error") },
    );
  }

  return (
    <div
      className="border-t border-dashed border-gray-200 bg-gray-50/70 px-5 py-4"
      onClick={(e) => e.stopPropagation()}
    >
      <p className="mb-3 text-[11px] text-slate-500">
        The risk level follows the cell on the 5x5 matrix.
      </p>
      <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
        <CellPicker label="Initial risk" cell={initial} onChange={setInitial} />
        <CellPicker
          label="Residual risk"
          cell={residual}
          onChange={setResidual}
          allowEmpty
        />
        <Button size="sm" disabled={!canSave} onClick={handleSave}>
          <Save size={14} className="mr-1" />
          Save rating
        </Button>
      </div>
      {residualHalfSet && (
        <p className="mt-2 text-[11px] text-amber-700">
          Choose both a likelihood and a severity for the residual risk, or
          clear both.
        </p>
      )}
    </div>
  );
}

function CellPicker({
  label,
  cell,
  onChange,
  allowEmpty = false,
}: {
  label: string;
  cell: MatrixCell;
  onChange: (cell: MatrixCell) => void;
  allowEmpty?: boolean;
}) {
  return (
    <fieldset>
      <legend className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </legend>
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label={`${label} likelihood`}
          value={cell.likelihood ?? ""}
          onChange={(e) =>
            onChange({ ...cell, likelihood: e.target.value || null })
          }
          className={SELECT_CLASS}
        >
          {allowEmpty && <option value="">Not recorded</option>}
          {LIKELIHOODS.map((l) => (
            <option key={l} value={l}>
              {l} – {LIKELIHOOD_LABELS[l].full}
            </option>
          ))}
        </select>
        <select
          aria-label={`${label} severity`}
          value={cell.severity ?? ""}
          onChange={(e) =>
            onChange({
              ...cell,
              severity: e.target.value ? Number(e.target.value) : null,
            })
          }
          className={SELECT_CLASS}
        >
          {allowEmpty && <option value="">Not recorded</option>}
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {SEVERITY_LABELS[s].short} – {SEVERITY_LABELS[s].full}
            </option>
          ))}
        </select>
        <RiskCellBadge
          likelihood={cell.likelihood}
          severity={cell.severity}
          level={levelFor(cell)}
        />
      </div>
    </fieldset>
  );
}
