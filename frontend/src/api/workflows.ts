import { apiClient } from "@/lib/api-client";
import type { DataResponse, PaginatedResponse } from "@/types/api";

export type WorkflowType = "phl" | "sra";
export type WorkflowStatus = "draft" | "submitted" | "approved" | "rejected";

export interface Workflow {
  id: string;
  organization_id: string;
  created_by: string;
  type: WorkflowType;
  status: WorkflowStatus;
  title: string;
  data: Record<string, unknown>;
  conversation_id: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  approved_by: string | null;
  risk_entry_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateWorkflowPayload {
  type: WorkflowType;
  title?: string;
  data?: Record<string, unknown>;
  conversation_id?: string | null;
}

export interface UpdateWorkflowPayload {
  title?: string;
  data?: Record<string, unknown>;
}

export async function createWorkflow(
  payload: CreateWorkflowPayload,
): Promise<Workflow> {
  const response = await apiClient.post<DataResponse<Workflow>>(
    "/workflows",
    payload,
  );
  return response.data.data;
}

export async function getWorkflow(id: string): Promise<Workflow> {
  const response = await apiClient.get<DataResponse<Workflow>>(
    `/workflows/${id}`,
  );
  return response.data.data;
}

export async function listWorkflows(params?: {
  type?: WorkflowType;
  status?: WorkflowStatus;
  skip?: number;
  limit?: number;
}): Promise<PaginatedResponse<Workflow>> {
  const response = await apiClient.get<PaginatedResponse<Workflow>>(
    "/workflows",
    { params },
  );
  return response.data;
}

export async function updateWorkflow(
  id: string,
  payload: UpdateWorkflowPayload,
): Promise<Workflow> {
  const response = await apiClient.patch<DataResponse<Workflow>>(
    `/workflows/${id}`,
    payload,
  );
  return response.data.data;
}

export async function submitWorkflow(id: string): Promise<Workflow> {
  const response = await apiClient.post<DataResponse<Workflow>>(
    `/workflows/${id}/submit`,
  );
  return response.data.data;
}

export async function approveWorkflow(
  id: string,
  approve: boolean,
  notes?: string,
): Promise<Workflow> {
  const response = await apiClient.post<DataResponse<Workflow>>(
    `/workflows/${id}/approve`,
    { approve, notes },
  );
  return response.data.data;
}

export async function deleteWorkflow(id: string): Promise<void> {
  await apiClient.delete(`/workflows/${id}`);
}
