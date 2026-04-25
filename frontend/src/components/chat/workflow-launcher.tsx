import type { FunctionType } from "@/types/api";

interface WorkflowOption {
  id: FunctionType;
  title: string;
  description: string;
}

const WORKFLOW_OPTIONS: WorkflowOption[] = [
  {
    id: "phl",
    title: "Preliminary Hazard List",
    description:
      "Identify hazards from a system change, new operation, or modified procedure.",
  },
  {
    id: "sra",
    title: "Safety Risk Assessment",
    description:
      "Score severity and likelihood, evaluate controls, and plan mitigations per AC 150/5200-37A.",
  },
  {
    id: "risk_register",
    title: "Add to Risk Register",
    description:
      "Record a hazard in the Airport Risk Register with category, scoring, and existing controls.",
  },
  {
    id: "system",
    title: "System Analysis",
    description:
      "Walk through a system change and analyze its safety impacts and dependencies.",
  },
];

interface WorkflowLauncherProps {
  activeFunction: FunctionType;
  onSelect: (fn: FunctionType) => void;
}

export function WorkflowLauncher({ activeFunction, onSelect }: WorkflowLauncherProps) {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6">
      <h2 className="mb-1 text-lg font-semibold text-slate-900">Start a workflow</h2>
      <p className="mb-4 text-sm text-slate-600">
        Pick a structured assessment, or just type a question below to chat freely.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {WORKFLOW_OPTIONS.map((option) => {
          const isActive = option.id === activeFunction;
          return (
            <button
              key={option.id}
              type="button"
              onClick={() => onSelect(option.id)}
              className={
                "flex flex-col items-start rounded-lg border p-4 text-left transition " +
                (isActive
                  ? "border-blue-500 bg-blue-50 ring-1 ring-blue-200"
                  : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50")
              }
            >
              <span className="text-sm font-semibold text-slate-900">{option.title}</span>
              <span className="mt-1 text-xs text-slate-600">{option.description}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
