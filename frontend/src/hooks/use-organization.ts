import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addMember,
  createOrganization,
  getOrganizationMembers,
  getOrganizations,
  removeMember,
  updateMemberRole,
} from "@/api/organizations";
import type { MembershipRole } from "@/types/api";

export function useOrganizations() {
  return useQuery({
    queryKey: ["organizations"],
    queryFn: getOrganizations,
  });
}

export function useOrganizationMembers(orgId: string | null) {
  return useQuery({
    queryKey: ["organization-members", orgId],
    queryFn: () => getOrganizationMembers(orgId!),
    enabled: !!orgId,
  });
}

export function useCreateOrganization() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: { name: string; slug: string; is_platform?: boolean }) =>
      createOrganization(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["organizations"] });
    },
  });
}

export function useAddMember(orgId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: { user_id?: string; email?: string; role: MembershipRole }) =>
      addMember(orgId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["organization-members", orgId] });
    },
  });
}

export function useUpdateMemberRole(orgId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: { userId: string; role: MembershipRole }) =>
      updateMemberRole(orgId, payload.userId, payload.role),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["organization-members", orgId] });
    },
  });
}

export function useRemoveMember(orgId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: string) => removeMember(orgId, userId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["organization-members", orgId] });
    },
  });
}
