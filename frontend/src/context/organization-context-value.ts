import { createContext } from "react";
import type { OrganizationSummary } from "@/types/api";

export interface OrganizationContextValue {
  organizations: OrganizationSummary[];
  activeOrganization: OrganizationSummary | null;
  setActiveOrganization: (org: OrganizationSummary) => void;
  isLoading: boolean;
}

export const OrganizationContext = createContext<OrganizationContextValue | null>(null);
