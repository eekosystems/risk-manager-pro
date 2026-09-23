import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";

import {
  confirmResidualAssessment,
  createMitigation,
  createRisk,
  deleteMitigation,
  deleteRisk,
  dismissResidualAssessment,
  getMitigations,
  getRisk,
  getRisks,
  importSrmdHazards,
  requestResidualAssessment,
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

// While any re-assessment is still running, poll so its proposal appears
// without a manual refresh.
const REASSESSMENT_POLL_MS = 5000;

export function useRisks(params?: GetRisksParams) {
  return useQuery({
    queryKey: ["risks", params],
    queryFn: () => getRisks(params),
    refetchInterval: (query) =>
      query.state.data?.data.some(
        (risk) => risk.latest_assessment?.status === "pending",
      )
        ? REASSESSMENT_POLL_MS
        : false,
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
    onSuccess: () => invalidateRisk(queryClient, riskId),
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
    onSuccess: () => invalidateRisk(queryClient, riskId),
  });
}

export function useDeleteMitigation(riskId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (mitigationId: string) =>
      deleteMitigation(riskId, mitigationId),
    onSuccess: () => invalidateRisk(queryClient, riskId),
  });
}

// A mitigation or residual change alters the record and the register row
// (a re-assessment is queued on every mitigation change).
function invalidateRisk(queryClient: QueryClient, riskId: string) {
  void queryClient.invalidateQueries({ queryKey: ["risk", riskId] });
  void queryClient.invalidateQueries({ queryKey: ["risks"] });
}

export function useImportSrmdHazards() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: importSrmdHazards,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["risks"] });
    },
  });
}

export function useRequestResidualAssessment(riskId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => requestResidualAssessment(riskId),
    onSuccess: () => invalidateRisk(queryClient, riskId),
  });
}

export function useConfirmResidualAssessment(riskId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assessmentId: string) =>
      confirmResidualAssessment(riskId, assessmentId),
    onSuccess: () => invalidateRisk(queryClient, riskId),
  });
}

export function useDismissResidualAssessment(riskId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assessmentId: string) =>
      dismissResidualAssessment(riskId, assessmentId),
    onSuccess: () => invalidateRisk(queryClient, riskId),
  });
}
