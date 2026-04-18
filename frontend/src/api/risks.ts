import { apiClient } from "@/lib/api-client";
import type {
  CreateMitigationRequest,
  CreateRiskEntryRequest,
  DataResponse,
  MitigationItem,
  PaginatedResponse,
  RiskEntryDetail,
  RiskEntryListItem,
  UpdateMitigationRequest,
  UpdateRiskEntryRequest,
} from "@/types/api";

export interface GetRisksParams {
  skip?: number;
  limit?: number;
  status?: string;
  risk_level?: string;
  airport_identifier?: string;
}

export async function getRisks(
  params: GetRisksParams = {},
): Promise<{ data: RiskEntryListItem[]; total: number }> {
  const response = await apiClient.get<PaginatedResponse<RiskEntryListItem>>(
    "/risks",
    { params },
  );
  return { data: response.data.data, total: response.data.meta.total };
}

export async function getRisk(riskId: string): Promise<RiskEntryDetail> {
  const response = await apiClient.get<DataResponse<RiskEntryDetail>>(
    `/risks/${riskId}`,
  );
  return response.data.data;
}

export async function createRisk(
  payload: CreateRiskEntryRequest,
): Promise<RiskEntryDetail> {
  const response = await apiClient.post<DataResponse<RiskEntryDetail>>(
    "/risks",
    payload,
  );
  return response.data.data;
}

export async function updateRisk(
  riskId: string,
  payload: UpdateRiskEntryRequest,
): Promise<RiskEntryDetail> {
  const response = await apiClient.patch<DataResponse<RiskEntryDetail>>(
    `/risks/${riskId}`,
    payload,
  );
  return response.data.data;
}

export async function deleteRisk(riskId: string): Promise<void> {
  await apiClient.delete(`/risks/${riskId}`);
}

export async function getMitigations(
  riskId: string,
): Promise<MitigationItem[]> {
  const response = await apiClient.get<DataResponse<MitigationItem[]>>(
    `/risks/${riskId}/mitigations`,
  );
  return response.data.data;
}

export async function createMitigation(
  riskId: string,
  payload: CreateMitigationRequest,
): Promise<MitigationItem> {
  const response = await apiClient.post<DataResponse<MitigationItem>>(
    `/risks/${riskId}/mitigations`,
    payload,
  );
  return response.data.data;
}

export async function updateMitigation(
  riskId: string,
  mitigationId: string,
  payload: UpdateMitigationRequest,
): Promise<MitigationItem> {
  const response = await apiClient.patch<DataResponse<MitigationItem>>(
    `/risks/${riskId}/mitigations/${mitigationId}`,
    payload,
  );
  return response.data.data;
}

export async function deleteMitigation(
  riskId: string,
  mitigationId: string,
): Promise<void> {
  await apiClient.delete(`/risks/${riskId}/mitigations/${mitigationId}`);
}
