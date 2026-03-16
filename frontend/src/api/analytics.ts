import { apiClient } from "@/lib/api-client";
import type { ActivityEntry, DashboardData, DataResponse } from "@/types/api";

export async function getDashboard(): Promise<DashboardData> {
  const response = await apiClient.get<DataResponse<DashboardData>>(
    "/analytics/dashboard",
  );
  return response.data.data;
}

export async function getRecentActivity(
  limit: number = 20,
): Promise<ActivityEntry[]> {
  const response = await apiClient.get<DataResponse<ActivityEntry[]>>(
    "/analytics/activity",
    { params: { limit } },
  );
  return response.data.data;
}
