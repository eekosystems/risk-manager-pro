import { apiClient } from "@/lib/api-client";
import type {
  DataResponse,
  MembershipRole,
  OrganizationDetail,
  OrganizationMember,
  OrganizationSummary,
} from "@/types/api";

export async function getOrganizations(): Promise<OrganizationSummary[]> {
  const response = await apiClient.get<DataResponse<OrganizationSummary[]>>("/organizations");
  return response.data.data;
}

export async function createOrganization(payload: {
  name: string;
  slug: string;
  is_platform?: boolean;
}): Promise<OrganizationDetail> {
  const response = await apiClient.post<DataResponse<OrganizationDetail>>(
    "/organizations",
    payload,
  );
  return response.data.data;
}

export async function getOrganization(orgId: string): Promise<OrganizationDetail> {
  const response = await apiClient.get<DataResponse<OrganizationDetail>>(
    `/organizations/${orgId}`,
  );
  return response.data.data;
}

export async function getOrganizationMembers(orgId: string): Promise<OrganizationMember[]> {
  const response = await apiClient.get<DataResponse<OrganizationMember[]>>(
    `/organizations/${orgId}/members`,
  );
  return response.data.data;
}

export async function addMember(
  orgId: string,
  payload: { user_id?: string; email?: string; role: MembershipRole },
): Promise<OrganizationMember> {
  const response = await apiClient.post<DataResponse<OrganizationMember>>(
    `/organizations/${orgId}/members`,
    payload,
  );
  return response.data.data;
}

export async function updateMemberRole(
  orgId: string,
  userId: string,
  role: MembershipRole,
): Promise<OrganizationMember> {
  const response = await apiClient.patch<DataResponse<OrganizationMember>>(
    `/organizations/${orgId}/members/${userId}`,
    { role },
  );
  return response.data.data;
}

export async function removeMember(orgId: string, userId: string): Promise<void> {
  await apiClient.delete(`/organizations/${orgId}/members/${userId}`);
}
