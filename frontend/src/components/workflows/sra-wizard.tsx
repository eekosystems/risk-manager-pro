import { useState } from "react";
import { AlertTriangle, MessageSquare } from "lucide-react";

import { Button } from "@/components/ui/button";
import { RiskMatrix } from "@/components/ui/risk-matrix";
import { useCreateRisk, useRisks, useUpdateRisk } from "@/hooks/use-risks";
import { useToast } from "@/hooks/use-toast";
import { useWorkflow } from "@/hooks/use-workflow";
import type { CreateRiskEntryRequest, RiskEntryListItem } from "@/types/api";
import {
  LIKELIHOOD_LABELS,
  RISK_LEVEL_CONFIG,
  RISK_MATRIX,
  SEVERITY_LABELS,
  type Likelihood,
  type RiskMatrixSelection,
  type Severity,
} from "@/types/risk-matrix";

import { AiAssistPanel } from "./ai-assist-panel";
import { WizardStep } from "./wizard-step";

const SRA_STEPS = [
  "Select Hazard",
  "Analyze Risk",
  "Assess ALARP",
  "Mitigations & Residual",
  "Review & Save",
];

interface SRAWorkflowData {
  sourceRiskId: string | null;
  title: string;
  description: string;
  hazard: string;
  initialSeverity: Severity;
  initialLikelihood: Likelihood;
  justification: string;
  residualSeverity: Severity;
  residualLikelihood: Likelihood;
  mitigations: { title: string; description: string }[];
}

interface SRAWizardProps {
  onComplete: () => void;
  onCancel: () => void;
}

export function SRAWizard({ onComplete, onCancel }: SRAWizardProps) {
  const { addToast } = useToast();
  const createRisk = useCreateRisk();
  const updateRisk = useUpdateRisk();
  const { data: risksData } = useRisks({ limit: 100 });
  const workflow = useWorkflow<SRAWorkflowData>({ totalSteps: 5 });
  const [showAiPanel, setShowAiPanel] = useState(false);

  const d = workflow.data;
  const risks = risksData?.data ?? [];

  const inputClass =
    "w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20";
  const labelClass = "block text-sm font-semibold text-slate-700 mb-1";

  const initialSelection: RiskMatrixSelection | null =
    d.initialSeverity && d.initialLikelihood
      ? {
          severity: d.initialSeverity,
          likelihood: d.initialLikelihood,
          riskLevel: RISK_MATRIX[d.initialLikelihood][d.initialSeverity],
        }
      : null;

  const residualSelection: RiskMatrixSelection | null =
    d.residualSeverity && d.residualLikelihood
      ? {
          severity: d.residualSeverity,
          likelihood: d.residualLikelihood,
          riskLevel: RISK_MATRIX[d.residualLikelihood][d.residualSeverity],
        }
      : null;

  function canProceed(): boolean {
    switch (workflow.currentStep) {
      case 0:
        return !!(d.title?.trim() && d.hazard?.trim());
      case 1:
        return !!(d.initialSeverity && d.initialLikelihood);
      case 2:
        return true;
      case 3:
        return !!(d.residualSeverity && d.residualLikelihood);
      default:
        return true;
    }
  }

  function handleSelectExistingRisk(risk: RiskEntryListItem) {
    workflow.updateData({
      sourceRiskId: risk.id,
      title: risk.title,
      hazard: risk.hazard,
      initialSeverity: risk.severity as Severity,
      initialLikelihood: risk.likelihood as Likelihood,
    } as Partial<SRAWorkflowData>);
  }

  function handleSave() {
    if (!d.title || !d.hazard || !d.residualSeverity || !d.residualLikelihood) return;

    const notes = [
      d.justification ? `Risk Analysis Justification: ${d.justification}` : "",
      initialSelection
        ? `Initial Risk: ${RISK_LEVEL_CONFIG[initialSelection.riskLevel].label} (Severity: ${SEVERITY_LABELS[d.initialSeverity!].full}, Likelihood: ${LIKELIHOOD_LABELS[d.initialLikelihood!].full})`
        : "",
      residualSelection
        ? `Residual Risk: ${RISK_LEVEL_CONFIG[residualSelection.riskLevel].label} (Severity: ${SEVERITY_LABELS[d.residualSeverity].full}, Likelihood: ${LIKELIHOOD_LABELS[d.residualLikelihood].full})`
        : "",
      d.mitigations?.length
        ? `Mitigations:\n${d.mitigations.map((m) => `- ${m.title}: ${m.description}`).join("\n")}`
        : "",
    ]
      .filter(Boolean)
      .join("\n\n") || null;

    if (d.sourceRiskId) {
      updateRisk.mutate(
        {
          riskId: d.sourceRiskId,
          payload: {
            severity: d.residualSeverity,
            likelihood: d.residualLikelihood,
            notes,
          },
        },
        {
          onSuccess: () => {
            addToast("Risk entry updated with SRA results", "success");
            onComplete();
          },
          onError: () => {
            addToast("Failed to update risk entry", "error");
          },
        },
      );
    } else {
      const payload: CreateRiskEntryRequest = {
        title: d.title,
        description: d.description ?? d.hazard,
        hazard: d.hazard,
        severity: d.residualSeverity,
        likelihood: d.residualLikelihood,
        function_type: "sra",
        conversation_id: workflow.conversationId,
        notes,
      };

      createRisk.mutate(payload, {
        onSuccess: () => {
          addToast("Risk entry saved to register", "success");
          onComplete();
        },
        onError: () => {
          addToast("Failed to save risk entry", "error");
        },
      });
    }
  }

  function getAiContext(): string {
    const parts = [
      `I'm conducting a Safety Risk Assessment (SRA) per AC 150/5200-37A Steps 3-5.`,
      d.title ? `Hazard: ${d.title}` : "",
      d.hazard ? `Description: ${d.hazard}` : "",
      initialSelection
        ? `Initial Risk Level: ${RISK_LEVEL_CONFIG[initialSelection.riskLevel].label}`
        : "",
      d.justification ? `Justification: ${d.justification}` : "",
    ];
    return parts.filter(Boolean).join("\n");
  }

  const isSaving = createRisk.isPending || updateRisk.isPending;

  const initialRiskLevel = initialSelection
    ? RISK_LEVEL_CONFIG[initialSelection.riskLevel]
    : null;

  const stepContent = [
    // Step 0: Select Hazard Source
    <div key="step-0" className="space-y-4">
      {risks.length > 0 && (
        <div>
          <label className={labelClass}>Select from Risk Register (optional)</label>
          <div className="max-h-[200px] overflow-y-auto rounded-xl border border-gray-200">
            {risks.map((risk) => (
              <button
                key={risk.id}
                onClick={() => handleSelectExistingRisk(risk)}
                className={`flex w-full items-center gap-3 border-b border-gray-100 px-4 py-3 text-left transition-colors hover:bg-brand-50 last:border-b-0 ${
                  d.sourceRiskId === risk.id ? "bg-brand-50" : ""
                }`}
              >
                <AlertTriangle size={14} className="text-brand-500" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-slate-800">
                    {risk.title}
                  </div>
                  <div className="truncate text-xs text-slate-400">
                    {risk.hazard}
                  </div>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${RISK_LEVEL_CONFIG[risk.risk_level as keyof typeof RISK_LEVEL_CONFIG]?.bg ?? ""} ${RISK_LEVEL_CONFIG[risk.risk_level as keyof typeof RISK_LEVEL_CONFIG]?.color ?? ""}`}
                >
                  {RISK_LEVEL_CONFIG[risk.risk_level as keyof typeof RISK_LEVEL_CONFIG]?.label ?? risk.risk_level}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="relative">
        {risks.length > 0 && (
          <div className="my-4 flex items-center gap-3">
            <div className="h-px flex-1 bg-gray-200" />
            <span className="text-xs font-medium text-gray-400">OR enter new hazard</span>
            <div className="h-px flex-1 bg-gray-200" />
          </div>
        )}
        <div className="space-y-3">
          <div>
            <label className={labelClass}>Hazard Title</label>
            <input
              type="text"
              value={d.title ?? ""}
              onChange={(e) => workflow.updateData({ title: e.target.value, sourceRiskId: null } as Partial<SRAWorkflowData>)}
              placeholder="Brief hazard title..."
              className={inputClass}
              maxLength={500}
            />
          </div>
          <div>
            <label className={labelClass}>Hazard Description</label>
            <textarea
              value={d.hazard ?? ""}
              onChange={(e) => workflow.updateData({ hazard: e.target.value, sourceRiskId: null } as Partial<SRAWorkflowData>)}
              placeholder="Describe the hazard..."
              className={`${inputClass} min-h-[80px] resize-y`}
            />
          </div>
        </div>
      </div>
    </div>,

    // Step 1: Analyze Risk
    <div key="step-1" className="space-y-4">
      <p className="text-sm text-slate-500">
        Set the initial risk scoring by selecting a cell on the matrix.
      </p>
      <RiskMatrix
        selection={initialSelection}
        onSelect={(sel) =>
          workflow.updateData({
            initialSeverity: sel.severity,
            initialLikelihood: sel.likelihood,
          } as Partial<SRAWorkflowData>)
        }
      />
      <div>
        <label className={labelClass}>Justification</label>
        <textarea
          value={d.justification ?? ""}
          onChange={(e) => workflow.updateData({ justification: e.target.value } as Partial<SRAWorkflowData>)}
          placeholder="Provide evidence-based justification for this risk scoring..."
          className={`${inputClass} min-h-[80px] resize-y`}
        />
      </div>
      <Button variant="secondary" onClick={() => setShowAiPanel(true)}>
        <MessageSquare size={16} className="mr-2" />
        Ask AI for Help
      </Button>
    </div>,

    // Step 2: Assess ALARP
    <div key="step-2" className="space-y-4">
      {initialRiskLevel && (
        <div
          className={`rounded-xl border p-4 ${initialRiskLevel.bg} ${initialRiskLevel.border}`}
        >
          <p className={`text-sm font-bold ${initialRiskLevel.color}`}>
            Initial Risk Level: {initialRiskLevel.label}
          </p>
          <p className="mt-1 text-xs text-slate-600">
            Severity: {d.initialSeverity ? SEVERITY_LABELS[d.initialSeverity].full : "—"} |
            Likelihood: {d.initialLikelihood ? LIKELIHOOD_LABELS[d.initialLikelihood].full : "—"}
          </p>
        </div>
      )}

      {initialSelection &&
        (initialSelection.riskLevel === "high" ||
          initialSelection.riskLevel === "serious") && (
          <div className="rounded-xl border border-red-300 bg-red-50 p-4">
            <p className="text-sm font-bold text-red-800">
              Accountable Executive Review Required
            </p>
            <p className="mt-1 text-xs text-red-600">
              This risk level requires explicit review and acceptance by the
              Accountable Executive before proceeding.
            </p>
          </div>
        )}

      <div className="rounded-xl border border-gray-200 bg-white p-4">
        <h4 className="text-sm font-bold text-slate-700">ALARP Assessment</h4>
        <p className="mt-2 text-xs text-slate-500">
          Determine whether risk is As Low As Reasonably Practicable. Consider
          the balance between cost/feasibility of further risk reduction and the
          residual risk level.
        </p>
      </div>

      <Button variant="secondary" onClick={() => setShowAiPanel(true)}>
        <MessageSquare size={16} className="mr-2" />
        Ask AI for Help
      </Button>
    </div>,

    // Step 3: Mitigations & Residual Risk
    <div key="step-3" className="space-y-6">
      <SRAMitigationStep
        mitigations={d.mitigations ?? []}
        onUpdate={(mitigations) => workflow.updateData({ mitigations } as Partial<SRAWorkflowData>)}
      />
      <div>
        <h4 className="mb-2 text-sm font-bold text-slate-700">Residual Risk Score</h4>
        <p className="mb-3 text-xs text-slate-500">
          After applying mitigations, set the expected residual risk level.
        </p>
        <RiskMatrix
          selection={residualSelection}
          onSelect={(sel) =>
            workflow.updateData({
              residualSeverity: sel.severity,
              residualLikelihood: sel.likelihood,
            } as Partial<SRAWorkflowData>)
          }
        />
      </div>
    </div>,

    // Step 4: Review & Save
    <div key="step-4" className="space-y-4">
      <div className="rounded-2xl border border-gray-200 bg-white p-5">
        <h3 className="text-sm font-bold text-slate-900">SRA Summary</h3>
        <div className="mt-3 space-y-2 text-sm text-slate-600">
          <div>
            <span className="font-semibold">Hazard:</span> {d.title}
          </div>
          <div>
            <span className="font-semibold">Description:</span> {d.hazard}
          </div>
          {d.justification && (
            <div>
              <span className="font-semibold">Justification:</span> {d.justification}
            </div>
          )}
        </div>

        {/* Before/After comparison */}
        <div className="mt-4 grid grid-cols-2 gap-3">
          {initialSelection && (
            <div
              className={`rounded-xl border p-3 ${RISK_LEVEL_CONFIG[initialSelection.riskLevel].bg} ${RISK_LEVEL_CONFIG[initialSelection.riskLevel].border}`}
            >
              <p className="text-xs font-medium text-slate-500">Initial Risk</p>
              <p
                className={`text-sm font-bold ${RISK_LEVEL_CONFIG[initialSelection.riskLevel].color}`}
              >
                {RISK_LEVEL_CONFIG[initialSelection.riskLevel].label}
              </p>
              <p className="text-[10px] text-slate-500">
                S: {SEVERITY_LABELS[d.initialSeverity!].full} / L:{" "}
                {LIKELIHOOD_LABELS[d.initialLikelihood!].full}
              </p>
            </div>
          )}
          {residualSelection && (
            <div
              className={`rounded-xl border p-3 ${RISK_LEVEL_CONFIG[residualSelection.riskLevel].bg} ${RISK_LEVEL_CONFIG[residualSelection.riskLevel].border}`}
            >
              <p className="text-xs font-medium text-slate-500">Residual Risk</p>
              <p
                className={`text-sm font-bold ${RISK_LEVEL_CONFIG[residualSelection.riskLevel].color}`}
              >
                {RISK_LEVEL_CONFIG[residualSelection.riskLevel].label}
              </p>
              <p className="text-[10px] text-slate-500">
                S: {SEVERITY_LABELS[d.residualSeverity!].full} / L:{" "}
                {LIKELIHOOD_LABELS[d.residualLikelihood!].full}
              </p>
            </div>
          )}
        </div>

        {d.mitigations && d.mitigations.length > 0 && (
          <div className="mt-4">
            <span className="text-sm font-semibold text-slate-700">
              Mitigations ({d.mitigations.length}):
            </span>
            <ul className="mt-1 list-disc pl-5 text-xs text-slate-500">
              {d.mitigations.map((m, i) => (
                <li key={i}>
                  <span className="font-medium text-slate-700">{m.title}</span>
                  {m.description && ` — ${m.description}`}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>,
  ];

  return (
    <div className="flex h-full">
      <div className="flex flex-1 flex-col">
        <WizardStep
          steps={SRA_STEPS}
          currentStep={workflow.currentStep}
          title={SRA_STEPS[workflow.currentStep] ?? ""}
          isFirst={workflow.isFirst}
          isLast={workflow.isLast}
          nextDisabled={workflow.isLast ? isSaving : !canProceed()}
          nextLabel={
            workflow.isLast
              ? isSaving
                ? "Saving..."
                : d.sourceRiskId
                  ? "Update Risk Entry"
                  : "Save to Risk Register"
              : undefined
          }
          onNext={workflow.isLast ? handleSave : workflow.next}
          onBack={workflow.isFirst ? onCancel : workflow.back}
        >
          {stepContent[workflow.currentStep]}
        </WizardStep>
      </div>

      <AiAssistPanel
        isOpen={showAiPanel}
        onClose={() => setShowAiPanel(false)}
        functionType="sra"
        contextMessage={getAiContext()}
        conversationId={workflow.conversationId}
        onConversationId={workflow.setConversationId}
      />
    </div>
  );
}

interface SRAMitigationStepProps {
  mitigations: { title: string; description: string }[];
  onUpdate: (mitigations: { title: string; description: string }[]) => void;
}

function SRAMitigationStep({ mitigations, onUpdate }: SRAMitigationStepProps) {
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");

  const inputClass =
    "w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

  function handleAdd() {
    if (!newTitle.trim()) return;
    onUpdate([...mitigations, { title: newTitle.trim(), description: newDesc.trim() }]);
    setNewTitle("");
    setNewDesc("");
  }

  function handleRemove(index: number) {
    onUpdate(mitigations.filter((_, i) => i !== index));
  }

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-bold text-slate-700">Define Mitigations</h4>
      <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
        <p className="mb-3 text-xs font-medium text-slate-500">
          Hierarchy of Controls: Avoid/Eliminate &gt; Substitute &gt; Engineer &gt; Administrative &gt; PPE
        </p>
        <div className="space-y-2">
          <input
            type="text"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="Mitigation title..."
            className={inputClass}
          />
          <textarea
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            placeholder="Describe the mitigation..."
            className={`${inputClass} min-h-[60px] resize-y`}
          />
          <div className="flex justify-end">
            <Button size="sm" onClick={handleAdd} disabled={!newTitle.trim()}>
              Add Mitigation
            </Button>
          </div>
        </div>
      </div>

      {mitigations.length > 0 && (
        <div className="space-y-2">
          {mitigations.map((m, i) => (
            <div
              key={i}
              className="flex items-start justify-between rounded-xl border border-gray-200 bg-white p-3"
            >
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold text-slate-800">
                  {m.title}
                </div>
                {m.description && (
                  <div className="mt-0.5 text-xs text-slate-500">
                    {m.description}
                  </div>
                )}
              </div>
              <button
                onClick={() => handleRemove(i)}
                className="ml-2 rounded-lg p-1 text-gray-300 transition-colors hover:bg-red-50 hover:text-red-500"
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
