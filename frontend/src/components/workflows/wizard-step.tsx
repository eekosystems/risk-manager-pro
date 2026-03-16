import { clsx } from "clsx";
import { ArrowLeft, ArrowRight, Check } from "lucide-react";

import { Button } from "@/components/ui/button";

interface WizardStepProps {
  steps: string[];
  currentStep: number;
  title: string;
  description?: string;
  children: React.ReactNode;
  onNext?: () => void;
  onBack?: () => void;
  isFirst: boolean;
  isLast: boolean;
  nextLabel?: string | undefined;
  nextDisabled?: boolean | undefined;
}

export function WizardStep({
  steps,
  currentStep,
  title,
  description,
  children,
  onNext,
  onBack,
  isFirst,
  isLast,
  nextLabel,
  nextDisabled,
}: WizardStepProps) {
  return (
    <div className="flex h-full flex-col">
      {/* Step indicator */}
      <div className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-3xl items-center gap-2">
          {steps.map((stepName, i) => (
            <div key={stepName} className="flex items-center gap-2">
              <div
                className={clsx(
                  "flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-colors",
                  i < currentStep
                    ? "bg-green-500 text-white"
                    : i === currentStep
                      ? "gradient-brand text-white shadow-md shadow-brand-500/20"
                      : "bg-gray-200 text-gray-500",
                )}
              >
                {i < currentStep ? <Check size={14} /> : i + 1}
              </div>
              <span
                className={clsx(
                  "hidden text-xs font-medium sm:inline",
                  i === currentStep ? "text-slate-800" : "text-gray-400",
                )}
              >
                {stepName}
              </span>
              {i < steps.length - 1 && (
                <div
                  className={clsx(
                    "h-px w-6",
                    i < currentStep ? "bg-green-400" : "bg-gray-200",
                  )}
                />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Step content */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-3xl">
          <h2 className="text-lg font-bold text-slate-900">{title}</h2>
          {description && (
            <p className="mt-1 text-sm text-slate-500">{description}</p>
          )}
          <div className="mt-6">{children}</div>
        </div>
      </div>

      {/* Navigation buttons */}
      <div className="border-t border-gray-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-3xl items-center justify-between">
          <Button
            variant="secondary"
            onClick={onBack}
            disabled={isFirst}
          >
            <ArrowLeft size={16} className="mr-2" />
            Back
          </Button>
          <Button onClick={onNext} disabled={nextDisabled}>
            {nextLabel ?? (isLast ? "Save" : "Next")}
            {!isLast && <ArrowRight size={16} className="ml-2" />}
          </Button>
        </div>
      </div>
    </div>
  );
}
