import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useUserRole } from "./use-user-role";

vi.mock("@azure/msal-react", () => ({
  useIsAuthenticated: () => true,
}));

vi.mock("@/hooks/use-organization-context", () => ({
  useOrganizationContext: () => ({
    organizations: [],
    activeOrganization: { id: "org-1", name: "Acme", slug: "acme", status: "active", is_platform: false },
    setActiveOrganization: () => {},
    isLoading: false,
  }),
}));

const getCurrentUserMock = vi.fn();
vi.mock("@/api/users", () => ({
  getCurrentUser: () => getCurrentUserMock(),
}));

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  getCurrentUserMock.mockReset();
});

describe("useUserRole", () => {
  it("marks org_admin as admin and canEdit", async () => {
    getCurrentUserMock.mockResolvedValue({
      id: "u1",
      email: "admin@example.com",
      display_name: "Admin",
      is_platform_admin: false,
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      last_login: null,
      organizations: [
        {
          organization_id: "org-1",
          organization_name: "Acme",
          role: "org_admin",
          is_active: true,
        },
      ],
    });

    const { result } = renderHook(() => useUserRole(), { wrapper });
    await waitFor(() => expect(result.current.role).toBe("org_admin"));
    expect(result.current.isAdmin).toBe(true);
    expect(result.current.canEdit).toBe(true);
  });

  it("viewer cannot edit", async () => {
    getCurrentUserMock.mockResolvedValue({
      id: "u2",
      email: "viewer@example.com",
      display_name: "Viewer",
      is_platform_admin: false,
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      last_login: null,
      organizations: [
        {
          organization_id: "org-1",
          organization_name: "Acme",
          role: "viewer",
          is_active: true,
        },
      ],
    });

    const { result } = renderHook(() => useUserRole(), { wrapper });
    await waitFor(() => expect(result.current.role).toBe("viewer"));
    expect(result.current.isAdmin).toBe(false);
    expect(result.current.canEdit).toBe(false);
  });

  it("platform admin overrides org role", async () => {
    getCurrentUserMock.mockResolvedValue({
      id: "u3",
      email: "platform@example.com",
      display_name: "Platform",
      is_platform_admin: true,
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      last_login: null,
      organizations: [],
    });

    const { result } = renderHook(() => useUserRole(), { wrapper });
    await waitFor(() => expect(result.current.isPlatformAdmin).toBe(true));
    expect(result.current.isAdmin).toBe(true);
    expect(result.current.canEdit).toBe(true);
  });
});
