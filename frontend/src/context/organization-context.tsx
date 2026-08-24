import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { useOrganizations } from "@/hooks/use-organization";
import { setActiveOrganizationId } from "@/lib/api-client";
import type { OrganizationSummary } from "@/types/api";

import { OrganizationContext } from "./organization-context-value";

const STORAGE_KEY = "rmp_active_org_id";

// The active organization scopes every retrieval: chat answers are filtered to
// this tenant's indexed documents. It was previously kept in sessionStorage,
// which does not survive a new window or a private/incognito session — so a
// fresh session silently fell back to the first organization alphabetically and
// queried the wrong document set with no visible indication. localStorage keeps
// the choice across windows; the header shows which organization is active so a
// wrong one is visible rather than silent.
function readStoredOrgId(): string | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return stored;
    // Migrate a choice made before this moved out of sessionStorage.
    const legacy = sessionStorage.getItem(STORAGE_KEY);
    if (legacy) {
      localStorage.setItem(STORAGE_KEY, legacy);
      sessionStorage.removeItem(STORAGE_KEY);
      return legacy;
    }
    return null;
  } catch {
    return null;
  }
}

interface OrganizationProviderProps {
  children: ReactNode;
}

export function OrganizationProvider({ children }: OrganizationProviderProps) {
  const { data: organizations = [], isLoading } = useOrganizations();
  const [activeOrganization, setActiveOrgState] = useState<OrganizationSummary | null>(null);

  const setActiveOrganization = useCallback((org: OrganizationSummary) => {
    setActiveOrgState(org);
    setActiveOrganizationId(org.id);
    try {
      localStorage.setItem(STORAGE_KEY, org.id);
    } catch {
      // Storage unavailable (private mode quota) — the choice still applies
      // for this session, it just won't persist to the next one.
    }
  }, []);

  useEffect(() => {
    if (organizations.length === 0 || activeOrganization) return;

    const savedId = readStoredOrgId();
    const saved = savedId ? organizations.find((o) => o.id === savedId) : null;

    if (saved) {
      setActiveOrganization(saved);
    } else {
      const first = organizations[0];
      if (first) setActiveOrganization(first);
    }
  }, [organizations, activeOrganization, setActiveOrganization]);

  const value = useMemo(
    () => ({
      organizations,
      activeOrganization,
      setActiveOrganization,
      isLoading,
    }),
    [organizations, activeOrganization, setActiveOrganization, isLoading],
  );

  return (
    <OrganizationContext.Provider value={value}>
      {children}
    </OrganizationContext.Provider>
  );
}