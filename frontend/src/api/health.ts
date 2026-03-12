import { apiClient } from "@/lib/api-client";

export interface HealthStatus {
  status: string;
  checks: Record<string, string>;
  checked_at: string;
}

export async function getHealthStatus(): Promise<HealthStatus> {
  const response = await apiClient.get<HealthStatus>("/health/ready");
  return response.data;
}
