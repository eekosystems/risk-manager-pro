import { apiClient } from "@/lib/api-client";
import type { DataResponse, UserProfile } from "@/types/api";

export async function getCurrentUser(): Promise<UserProfile> {
  const response = await apiClient.get<DataResponse<UserProfile>>("/users/me");
  return response.data.data;
}
