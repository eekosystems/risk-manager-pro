import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import {
  approveWorkflow,
  createWorkflow,
  deleteWorkflow,
  getWorkflow,
  listWorkflows,
  submitWorkflow,
  updateWorkflow,
  type CreateWorkflowPayload,
  type UpdateWorkflowPayload,
  type WorkflowStatus,
  type WorkflowType,
} from "@/api/workflows";

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

export function useWorkflowList(params?: {
  type?: WorkflowType;
  status?: WorkflowStatus;
}) {
  return useQuery({
    queryKey: ["workflows", params ?? {}],
    queryFn: () => listWorkflows(params),
  });
}

export function useWorkflowDetail(id: string | null) {
  return useQuery({
    queryKey: ["workflow", id],
    queryFn: () => getWorkflow(id!),
    enabled: !!id,
  });
}

export function useCreateWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateWorkflowPayload) => createWorkflow(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["workflows"] });
    },
  });
}

export function useUpdateWorkflow(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: UpdateWorkflowPayload) => updateWorkflow(id, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["workflow", id] });
      void qc.invalidateQueries({ queryKey: ["workflows"] });
    },
  });
}

export function useSubmitWorkflow(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => submitWorkflow(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["workflow", id] });
      void qc.invalidateQueries({ queryKey: ["workflows"] });
    },
  });
}

export function useApproveWorkflow(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { approve: boolean; notes?: string }) =>
      approveWorkflow(id, args.approve, args.notes),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["workflow", id] });
      void qc.invalidateQueries({ queryKey: ["workflows"] });
      void qc.invalidateQueries({ queryKey: ["risks"] });
    },
  });
}

export function useDeleteWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteWorkflow(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["workflows"] });
    },
  });
}
