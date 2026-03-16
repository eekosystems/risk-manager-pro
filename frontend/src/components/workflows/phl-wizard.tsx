import { useState } from "react";
import { MessageSquare } from "lucide-react";

import { Button } from "@/components/ui/button";
import { RiskMatrix } from "@/components/ui/risk-matrix";
import { useCreateRisk } from "@/hooks/use-risks";
import { useToast } from "@/hooks/use-toast";
import { useWorkflow } from "@/hooks/use-workflow";
import type { CreateRiskEntryRequest } from "@/types/api";
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

const PHL_STEPS = [
  "Describe System",
  "Identify Hazards",
  "Assess Risk",
  "Mitigations",
  "Review & Save",
];

interface PHLWorkflowData {
  title: string;
  description: string;
  affectedArea: string;
  existingControls: string;
  hazard: string;
  hazardCategory: string;
  severity: Severity;
  likelihood: Likelihood;
  mitigations: { title: string; description: string }[];
}

interface PHLWizardProps {
  onComplete: () => void;
  onCancel: () => void;
}

export function PHLWizard({ onComplete, onCancel }: PHLWizardProps) {
  const { addToast } = useToast();
  const createRisk = useCreateRisk();
  const workflow = useWorkflow<PHLWorkflowData>({ totalSteps: 5 });
  const [showAiPanel, setShowAiPanel] = useState(false);

  const d = workflow.data;
  const inputClass =
    "w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20";
  const labelClass = "block text-sm font-semibold text-slate-700 mb-1";

  const matrixSelection: RiskMatrixSelection | null =
    d.severity && d.likelihood
      ? {
          severity: d.severity,
          likelihood: d.likelihood,
          riskLevel: RISK_MATRIX[d.likelihood][d.severity],
        }
      : null;

  function canProceed(): boolean {
    switch (workflow.currentStep) {
      case 0:
        return !!(d.title?.trim() && d.description?.trim());
      case 1:
        return !!(d.hazard?.trim());
      case 2:
        return !!(d.severity && d.likelihood);
      default:
        return true;
    }
  }

  function handleSave() {
    if (!d.title || !d.hazard || !d.description || !d.severity || !d.likelihood) return;

    const payload: CreateRiskEntryRequest = {
      title: d.title,
      description: d.description,
      hazard: d.hazard,
      severity: d.severity,
      likelihood: d.likelihood,
      function_type: "phl",
      conversation_id: workflow.conversationId,
      notes: [
        d.affectedArea ? `Affected Area: ${d.affectedArea}` : "",
        d.existingControls ? `Existing Controls: ${d.existingControls}` : "",
        d.hazardCategory ? `Hazard Category: ${d.hazardCategory}` : "",
        d.mitigations?.length
          ? `Proposed Mitigations:\n${d.mitigations.map((m) => `- ${m.title}: ${m.description}`).join("\n")}`
          : "",
      ]
        .filter(Boolean)
        .join("\n\n") || null,
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

  function getAiContext(): string {
    const parts = [
      `I'm conducting a Preliminary Hazard List (PHL) analysis.`,
      d.title ? `System/Change: ${d.title}` : "",
      d.description ? `Description: ${d.description}` : "",
      d.affectedArea ? `Affected Area: ${d.affectedArea}` : "",
      d.existingControls ? `Existing Controls: ${d.existingControls}` : "",
      d.hazard ? `Identified Hazard: ${d.hazard}` : "",
      d.hazardCategory ? `Hazard Category: ${d.hazardCategory}` : "",
    ];
    return parts.filter(Boolean).join("\n");
  }

  const stepContent = [
    // Step 0: Describe the System
    <div key="step-0" className="space-y-4">
      <div>
        <label className={labelClass}>Title / System Change</label>
        <input
          type="text"
          value={d.title ?? ""}
          onChange={(e) => workflow.updateData({ title: e.target.value } as Partial<PHLWorkflowData>)}
          placeholder="e.g., Runway 9/27 construction project..."
          className={inputClass}
          maxLength={500}
        />
      </div>
      <div>
        <label className={labelClass}>Description</label>
        <textarea
          value={d.description ?? ""}
          onChange={(e) => workflow.updateData({ description: e.target.value } as Partial<PHLWorkflowData>)}
          placeholder="Describe the system, proposed change, or operational context..."
          className={`${inputClass} min-h-[100px] resize-y`}
        />
      </div>
      <div>
        <label className={labelClass}>Affected Area</label>
        <select
          value={d.affectedArea ?? ""}
          onChange={(e) => workflow.updateData({ affectedArea: e.target.value } as Partial<PHLWorkflowData>)}
          className={inputClass}
        >
          <option value="">Select area...</option>
          <option value="movement">Movement Area</option>
          <option value="non-movement">Non-Movement Area</option>
          <option value="both">Both</option>
          <option value="other">Other</option>
        </select>
      </div>
      <div>
        <label className={labelClass}>Existing Controls (optional)</label>
        <textarea
          value={d.existingControls ?? ""}
          onChange={(e) => workflow.updateData({ existingControls: e.target.value } as Partial<PHLWorkflowData>)}
          placeholder="Describe any existing safety controls..."
          className={`${inputClass} min-h-[60px] resize-y`}
        />
      </div>
    </div>,

    // Step 1: Identify Hazards
    <div key="step-1" className="space-y-4">
      <div>
        <label className={labelClass}>Hazard Description</label>
        <textarea
          value={d.hazard ?? ""}
          onChange={(e) => workflow.updateData({ hazard: e.target.value } as Partial<PHLWorkflowData>)}
          placeholder="Describe the identified hazard..."
          className={`${inputClass} min-h-[100px] resize-y`}
        />
      </div>
      <div>
        <label className={labelClass}>Hazard Category</label>
        <select
          value={d.hazardCategory ?? ""}
          onChange={(e) => workflow.updateData({ hazardCategory: e.target.value } as Partial<PHLWorkflowData>)}
          className={inputClass}
        >
          <option value="">Select category...</option>
          <option value="technical">Technical</option>
          <option value="human">Human Factors</option>
          <option value="organizational">Organizational</option>
          <option value="environmental">Environmental</option>
        </select>
      </div>
      <Button
        variant="secondary"
        onClick={() => setShowAiPanel(true)}
      >
        <MessageSquare size={16} className="mr-2" />
        Ask AI for Help
      </Button>
    </div>,

    // Step 2: Assess Risk
    <div key="step-2" className="space-y-4">
      <p className="text-sm text-slate-500">
        Click a cell on the matrix below to set the severity and likelihood for this hazard.
      </p>
      <RiskMatrix
        selection={matrixSelection}
        onSelect={(sel) =>
          workflow.updateData({
            severity: sel.severity,
            likelihood: sel.likelihood,
          } as Partial<PHLWorkflowData>)
        }
      />
      <Button
        variant="secondary"
        onClick={() => setShowAiPanel(true)}
      >
        <MessageSquare size={16} className="mr-2" />
        Ask AI for Help
      </Button>
    </div>,

    // Step 3: Mitigations
    <MitigationStep
      key="step-3"
      mitigations={d.mitigations ?? []}
      onUpdate={(mitigations) => workflow.updateData({ mitigations } as Partial<PHLWorkflowData>)}
    />,

    // Step 4: Review & Save
    <div key="step-4" className="space-y-4">
      <div className="rounded-2xl border border-gray-200 bg-white p-5">
        <h3 className="text-sm font-bold text-slate-900">Summary</h3>
        <div className="mt-3 space-y-2 text-sm text-slate-600">
          <div>
            <span className="font-semibold">Title:</span> {d.title}
          </div>
          <div>
            <span className="font-semibold">Description:</span> {d.description}
          </div>
          {d.affectedArea && (
            <div>
              <span className="font-semibold">Affected Area:</span> {d.affectedArea}
            </div>
          )}
          <div>
            <span className="font-semibold">Hazard:</span> {d.hazard}
          </div>
          {d.hazardCategory && (
            <div>
              <span className="font-semibold">Category:</span> {d.hazardCategory}
            </div>
          )}
          {matrixSelection && (
            <div
              className={`mt-3 rounded-xl border p-3 ${RISK_LEVEL_CONFIG[matrixSelection.riskLevel].bg} ${RISK_LEVEL_CONFIG[matrixSelection.riskLevel].border}`}
            >
              <span
                className={`text-sm font-bold ${RISK_LEVEL_CONFIG[matrixSelection.riskLevel].color}`}
              >
                Risk Level: {RISK_LEVEL_CONFIG[matrixSelection.riskLevel].label}
              </span>
              <span className="ml-3 text-xs text-slate-600">
                Severity: {SEVERITY_LABELS[d.severity!].full} | Likelihood:{" "}
                {LIKELIHOOD_LABELS[d.likelihood!].full}
              </span>
            </div>
          )}
          {d.mitigations && d.mitigations.length > 0 && (
            <div className="mt-3">
              <span className="font-semibold">
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
      </div>
    </div>,
  ];

  return (
    <div className="flex h-full">
      <div className="flex flex-1 flex-col">
        <WizardStep
          steps={PHL_STEPS}
          currentStep={workflow.currentStep}
          title={PHL_STEPS[workflow.currentStep] ?? ""}
          isFirst={workflow.isFirst}
          isLast={workflow.isLast}
          nextDisabled={
            workflow.isLast ? createRisk.isPending : !canProceed()
          }
          nextLabel={
            workflow.isLast
              ? createRisk.isPending
                ? "Saving..."
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
        functionType="phl"
        contextMessage={getAiContext()}
        conversationId={workflow.conversationId}
        onConversationId={workflow.setConversationId}
      />
    </div>
  );
}

interface MitigationStepProps {
  mitigations: { title: string; description: string }[];
  onUpdate: (mitigations: { title: string; description: string }[]) => void;
}

function MitigationStep({ mitigations, onUpdate }: MitigationStepProps) {
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
    <div className="space-y-4">
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
            placeholder="Describe the mitigation action..."
            className={`${inputClass} min-h-[60px] resize-y`}
          />
          <div className="flex justify-end">
            <Button
              size="sm"
              onClick={handleAdd}
              disabled={!newTitle.trim()}
            >
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
