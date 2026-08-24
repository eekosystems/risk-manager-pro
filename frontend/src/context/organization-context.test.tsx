import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useOrganizationContext } from "@/hooks/use-organization-context";
import type { OrganizationSummary } from "@/types/api";

import { OrganizationProvider } from "./organization-context";

const ORGS: OrganizationSummary[] = [
  { id: "org-aaa", name: "Aardvark Airport", slug: "aaa", status: "active", is_platform: false },
  { id: "org-sat", name: "San Antonio (SAT)", slug: "sat", status: "active", is_platform: false },
];

vi.mock("@/hooks/use-organization", () => ({
  useOrganizations: () => ({ data: ORGS, isLoading: false }),
}));

const setActiveOrganizationId = vi.fn();
vi.mock("@/lib/api-client", () => ({
  setActiveOrganizationId: (id: string | null) => setActiveOrganizationId(id),
}));

function ActiveOrgProbe() {
  const { activeOrganization } = useOrganizationContext();
  return <span data-testid="active">{activeOrganization?.id ?? "none"}</span>;
}

function renderProvider() {
  return render(
    <OrganizationProvider>
      <ActiveOrgProbe />
    </OrganizationProvider>,
  );
}

describe("OrganizationProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    setActiveOrganizationId.mockClear();
  });

  it("restores the previously selected organization", async () => {
    localStorage.setItem("rmp_active_org_id", "org-sat");

    renderProvider();

    await waitFor(() => expect(screen.getByTestId("active")).toHaveTextContent("org-sat"));
    expect(setActiveOrganizationId).toHaveBeenCalledWith("org-sat");
  });

  it("persists the selection to localStorage so a new window keeps it", async () => {
    // Regression: the choice used to live in sessionStorage, so a new window or
    // a private session silently fell back to the first org alphabetically and
    // queried a different tenant's documents.
    renderProvider();

    await waitFor(() => expect(screen.getByTestId("active")).toHaveTextContent("org-aaa"));
    expect(localStorage.getItem("rmp_active_org_id")).toBe("org-aaa");
  });

  it("migrates a selection left behind in sessionStorage", async () => {
    sessionStorage.setItem("rmp_active_org_id", "org-sat");

    renderProvider();

    await waitFor(() => expect(screen.getByTestId("active")).toHaveTextContent("org-sat"));
    expect(localStorage.getItem("rmp_active_org_id")).toBe("org-sat");
    expect(sessionStorage.getItem("rmp_active_org_id")).toBeNull();
  });

  it("ignores a stored organization the user no longer belongs to", async () => {
    localStorage.setItem("rmp_active_org_id", "org-removed");

    renderProvider();

    await waitFor(() => expect(screen.getByTestId("active")).toHaveTextContent("org-aaa"));
  });
});
