import { useCallback, useState } from "react";

export interface UseWorkflowOptions {
  totalSteps: number;
}

export interface UseWorkflowReturn<T> {
  currentStep: number;
  data: Partial<T>;
  conversationId: string | null;
  setConversationId: (id: string | null) => void;
  updateData: (partial: Partial<T>) => void;
  next: () => void;
  back: () => void;
  goToStep: (step: number) => void;
  isFirst: boolean;
  isLast: boolean;
  reset: () => void;
}

export function useWorkflow<T>(
  options: UseWorkflowOptions,
): UseWorkflowReturn<T> {
  const [currentStep, setCurrentStep] = useState(0);
  const [data, setData] = useState<Partial<T>>({});
  const [conversationId, setConversationId] = useState<string | null>(null);

  const next = useCallback(() => {
    setCurrentStep((s) => Math.min(s + 1, options.totalSteps - 1));
  }, [options.totalSteps]);

  const back = useCallback(() => {
    setCurrentStep((s) => Math.max(s - 1, 0));
  }, []);

  const goToStep = useCallback(
    (step: number) => {
      if (step >= 0 && step < options.totalSteps) {
        setCurrentStep(step);
      }
    },
    [options.totalSteps],
  );

  const updateData = useCallback((partial: Partial<T>) => {
    setData((prev) => ({ ...prev, ...partial }));
  }, []);

  const reset = useCallback(() => {
    setCurrentStep(0);
    setData({});
    setConversationId(null);
  }, []);

  return {
    currentStep,
    data,
    conversationId,
    setConversationId,
    updateData,
    next,
    back,
    goToStep,
    isFirst: currentStep === 0,
    isLast: currentStep === options.totalSteps - 1,
    reset,
  };
}
