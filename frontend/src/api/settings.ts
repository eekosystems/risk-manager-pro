import { apiClient } from "@/lib/api-client";
import type { DataResponse } from "@/types/api";

export interface SettingsResponse<T = Record<string, unknown>> {
  category: string;
  settings: T;
  updated_at: string | null;
}

export interface RagSettings {
  chunk_size: number;
  chunk_overlap: number;
  top_k: number;
  score_threshold: number;
  search_type: "hybrid" | "vector" | "keyword";
  embedding_model: string;
  rerank_enabled: boolean;
  max_context_tokens: number;
}

export interface ModelSettings {
  chat_model: string;
  temperature: number;
  max_output_tokens: number;
  top_p: number;
  frequency_penalty: number;
  presence_penalty: number;
  stream_responses: boolean;
}

export interface PromptsSettings {
  system_prompt: string;
  phl_prompt: string;
  sra_prompt: string;
  system_analysis_prompt: string;
}

export async function getAllSettings(): Promise<SettingsResponse[]> {
  const response = await apiClient.get<DataResponse<SettingsResponse[]>>(
    "/settings",
  );
  return response.data.data;
}

export async function getSettingsByCategory<T = Record<string, unknown>>(
  category: string,
): Promise<SettingsResponse<T>> {
  const response = await apiClient.get<DataResponse<SettingsResponse<T>>>(
    `/settings/${category}`,
  );
  return response.data.data;
}

export async function updateRagSettings(
  payload: RagSettings,
): Promise<SettingsResponse> {
  const response = await apiClient.put<DataResponse<SettingsResponse>>(
    "/settings/rag",
    payload,
  );
  return response.data.data;
}

export async function updateModelSettings(
  payload: ModelSettings,
): Promise<SettingsResponse> {
  const response = await apiClient.put<DataResponse<SettingsResponse>>(
    "/settings/model",
    payload,
  );
  return response.data.data;
}

export async function updatePromptsSettings(
  payload: PromptsSettings,
): Promise<SettingsResponse> {
  const response = await apiClient.put<DataResponse<SettingsResponse>>(
    "/settings/prompts",
    payload,
  );
  return response.data.data;
}

export interface QaqcSettings {
  reviewer_user_ids: string[];
  notify_on_chat: boolean;
  notify_on_risk_created: boolean;
}

export async function updateQaqcSettings(
  payload: QaqcSettings,
): Promise<SettingsResponse> {
  const response = await apiClient.put<DataResponse<SettingsResponse>>(
    "/settings/qaqc",
    payload,
  );
  return response.data.data;
}
