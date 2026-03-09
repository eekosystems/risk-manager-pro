import { useContext } from "react";
import {
  OrganizationContext,
  type OrganizationContextValue,
} from "@/context/organization-context-value";

export function useOrganizationContext(): OrganizationContextValue {
  const ctx = useContext(OrganizationContext);
  if (!ctx) {
    throw new Error(
      "useOrganizationContext must be used within an OrganizationProvider",
    );
  }
  return ctx;
}
