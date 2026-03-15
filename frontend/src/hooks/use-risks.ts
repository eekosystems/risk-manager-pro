import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createMitigation,
  createRisk,
  deleteMitigation,
  deleteRisk,
  getMitigations,
  getRisk,
  getRisks,
  updateMitigation,
  updateRisk,
  type GetRisksParams,
} from "@/api/risks";
import type {
  CreateMitigationRequest,
  CreateRiskEntryRequest,
  UpdateMitigationRequest,
  UpdateRiskEntryRequest,
} from "@/types/api";

export function useRisks(params?: GetRisksParams) {
  return useQuery({
    queryKey: ["risks", params],
    queryFn: () => getRisks(params),
  });
}

export function useRisk(riskId: string | null) {
  return useQuery({
    queryKey: ["risk", riskId],
    queryFn: () => getRisk(riskId!),
    enabled: !!riskId,
  });
}

export function useCreateRisk() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateRiskEntryRequest) => createRisk(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["risks"] });
    },
  });
}

export function useUpdateRisk() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      riskId,
      payload,
    }: {
      riskId: string;
      payload: UpdateRiskEntryRequest;
    }) => updateRisk(riskId, payload),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["risks"] });
      void queryClient.invalidateQueries({
        queryKey: ["risk", variables.riskId],
      });
    },
  });
}

export function useDeleteRisk() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (riskId: string) => deleteRisk(riskId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["risks"] });
    },
  });
}

export function useMitigations(riskId: string | null) {
  return useQuery({
    queryKey: ["risk", riskId, "mitigations"],
    queryFn: () => getMitigations(riskId!),
    enabled: !!riskId,
  });
}

export function useCreateMitigation(riskId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateMitigationRequest) =>
      createMitigation(riskId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["risk", riskId] });
    },
  });
}

export function useUpdateMitigation(riskId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      mitigationId,
      payload,
    }: {
      mitigationId: string;
      payload: UpdateMitigationRequest;
    }) => updateMitigation(riskId, mitigationId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["risk", riskId] });
    },
  });
}

export function useDeleteMitigation(riskId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (mitigationId: string) =>
      deleteMitigation(riskId, mitigationId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["risk", riskId] });
    },
  });
}
