import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { useOrganizations } from "@/hooks/use-organization";
import { setActiveOrganizationId } from "@/lib/api-client";
import type { OrganizationSummary } from "@/types/api";

interface OrganizationContextValue {
  organizations: OrganizationSummary[];
  activeOrganization: OrganizationSummary | null;
  setActiveOrganization: (org: OrganizationSummary) => void;
  isLoading: boolean;
}

const OrganizationContext = createContext<OrganizationContextValue | null>(null);

const STORAGE_KEY = "rmp_active_org_id";

interface OrganizationProviderProps {
  children: ReactNode;
}

export function OrganizationProvider({ children }: OrganizationProviderProps) {
  const { data: organizations = [], isLoading } = useOrganizations();
  const [activeOrganization, setActiveOrgState] = useState<OrganizationSummary | null>(null);

  const setActiveOrganization = useCallback((org: OrganizationSummary) => {
    setActiveOrgState(org);
    setActiveOrganizationId(org.id);
    sessionStorage.setItem(STORAGE_KEY, org.id);
  }, []);

  useEffect(() => {
    if (organizations.length === 0 || activeOrganization) return;

    const savedId = sessionStorage.getItem(STORAGE_KEY);
    const saved = savedId ? organizations.find((o) => o.id === savedId) : null;

    if (saved) {
      setActiveOrganization(saved);
    } else {
      setActiveOrganization(organizations[0]);
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

export function useOrganizationContext(): OrganizationContextValue {
  const ctx = useContext(OrganizationContext);
  if (!ctx) {
    throw new Error("useOrganizationContext must be used within an OrganizationProvider");
  }
  return ctx;
}
