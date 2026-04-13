import { useIsAuthenticated } from "@azure/msal-react";
import { useQuery } from "@tanstack/react-query";

import { getCurrentUser } from "@/api/users";
import { useOrganizationContext } from "@/hooks/use-organization-context";
import type { MembershipRole, UserProfile } from "@/types/api";

interface UserRoleState {
  profile: UserProfile | undefined;
  role: MembershipRole | null;
  isAdmin: boolean;
  isAnalyst: boolean;
  isViewer: boolean;
  canEdit: boolean;
  isPlatformAdmin: boolean;
  isLoading: boolean;
}

export function useCurrentUser() {
  const isAuthenticated = useIsAuthenticated();
  return useQuery({
    queryKey: ["current-user"],
    queryFn: getCurrentUser,
    enabled: isAuthenticated,
    staleTime: 60_000,
  });
}

export function useUserRole(): UserRoleState {
  const { data: profile, isLoading } = useCurrentUser();
  const { activeOrganization } = useOrganizationContext();

  const role =
    profile?.organizations.find(
      (m) => m.organization_id === activeOrganization?.id && m.is_active,
    )?.role ?? null;

  const isPlatformAdmin = profile?.is_platform_admin ?? false;
  const isAdmin = isPlatformAdmin || role === "org_admin";
  const isAnalyst = role === "analyst";
  const isViewer = role === "viewer";
  const canEdit = isPlatformAdmin || role === "org_admin" || role === "analyst";

  return {
    profile,
    role,
    isAdmin,
    isAnalyst,
    isViewer,
    canEdit,
    isPlatformAdmin,
    isLoading,
  };
}
