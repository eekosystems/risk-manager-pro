import { apiClient } from "@/lib/api-client";
import type { DataResponse, UserProfile } from "@/types/api";

export async function getCurrentUser(): Promise<UserProfile> {
  const response = await apiClient.get<DataResponse<UserProfile>>("/users/me");
  return response.data.data;
}

/**
 * Grant or revoke platform administration. Platform admins only. The API
 * refuses changing your own flag and removing the last platform admin.
 */
export async function setPlatformAdmin(
  userId: string,
  isPlatformAdmin: boolean,
): Promise<void> {
  await apiClient.patch(`/users/${userId}/platform-admin`, {
    is_platform_admin: isPlatformAdmin,
  });
}
