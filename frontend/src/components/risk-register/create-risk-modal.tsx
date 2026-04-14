import { useState } from "react";
import { Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { CreateRiskEntryRequest, RiskEntryDetail } from "@/types/api";
import {
  LIKELIHOODS,
  LIKELIHOOD_LABELS,
  RISK_LEVEL_CONFIG,
  RISK_MATRIX,
  SEVERITIES,
  SEVERITY_LABELS,
  type Likelihood,
  type Severity,
} from "@/types/risk-matrix";

interface CreateRiskModalProps {
  onClose: () => void;
  onSubmit: (payload: CreateRiskEntryRequest) => void;
  isPending: boolean;
  existingRisk?: RiskEntryDetail;
  defaultFunctionType?: string;
  conversationId?: string | null;
}

export function CreateRiskModal({
  onClose,
  onSubmit,
  isPending,
  existingRisk,
  defaultFunctionType,
  conversationId,
}: CreateRiskModalProps) {
  const [hazard, setHazard] = useState(
    existingRisk?.hazard ?? existingRisk?.title ?? "",
  );
  const [description, setDescription] = useState(existingRisk?.description ?? "");
  const [severity, setSeverity] = useState<Severity>(
    (existingRisk?.severity as Severity) ?? 3,
  );
  const [likelihood, setLikelihood] = useState<Likelihood>(
    (existingRisk?.likelihood as Likelihood) ?? "C",
  );
  const [notes, setNotes] = useState(existingRisk?.notes ?? "");

  const functionType =
    existingRisk?.function_type ?? defaultFunctionType ?? "general";
  const computedRiskLevel = RISK_MATRIX[likelihood][severity];
  const riskConfig = RISK_LEVEL_CONFIG[computedRiskLevel];

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmedHazard = hazard.trim();
    if (!trimmedHazard || !description.trim()) return;
    onSubmit({
      title: trimmedHazard.slice(0, 500),
      description: description.trim(),
      hazard: trimmedHazard,
      severity,
      likelihood,
      function_type: functionType,
      conversation_id: conversationId ?? null,
      notes: notes.trim() || null,
    });
  }

  const inputClass =
    "w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20";
  const labelClass = "block text-sm font-semibold text-slate-700 mb-1";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-2xl rounded-2xl bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
          <h2 className="text-lg font-bold text-slate-900">
            {existingRisk ? "Edit Risk Entry" : "New Risk Entry"}
          </h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
          >
            <X size={20} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="max-h-[70vh] overflow-y-auto px-6 py-5">
          <div className="space-y-4">
            <div>
              <label className={labelClass}>Hazard</label>
              <input
                type="text"
                value={hazard}
                onChange={(e) => setHazard(e.target.value)}
                placeholder="Identified hazard..."
                className={inputClass}
                required
                maxLength={500}
              />
            </div>

            <div>
              <label className={labelClass}>Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Detailed risk description..."
                className={`${inputClass} min-h-[80px] resize-y`}
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Severity</label>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(Number(e.target.value) as Severity)}
                  className={inputClass}
                >
                  {SEVERITIES.map((s) => (
                    <option key={s} value={s}>
                      {s} — {SEVERITY_LABELS[s].full}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className={labelClass}>Likelihood</label>
                <select
                  value={likelihood}
                  onChange={(e) => setLikelihood(e.target.value as Likelihood)}
                  className={inputClass}
                >
                  {LIKELIHOODS.map((l) => (
                    <option key={l} value={l}>
                      {l} — {LIKELIHOOD_LABELS[l].full}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Live risk level display */}
            <div
              className={`rounded-xl border p-3 ${riskConfig.bg} ${riskConfig.border}`}
            >
              <span className={`text-sm font-bold ${riskConfig.color}`}>
                Computed Risk Level: {riskConfig.label}
              </span>
            </div>

            <div>
              <label className={labelClass}>Notes (optional)</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Additional notes..."
                className={`${inputClass} min-h-[60px] resize-y`}
              />
            </div>
          </div>

          {/* Footer */}
          <div className="mt-6 flex items-center justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending || !hazard.trim() || !description.trim()}>
              {isPending ? (
                <>
                  <Loader2 size={16} className="mr-2 animate-spin" />
                  Saving...
                </>
              ) : existingRisk ? (
                "Update Risk"
              ) : (
                "Create Risk"
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
