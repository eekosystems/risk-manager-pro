import { useQuery } from "@tanstack/react-query";

import {
  getAuditEntries,
  getAuditFilterOptions,
  type GetAuditParams,
} from "@/api/audit";

export function useAuditEntries(params: GetAuditParams) {
  return useQuery({
    queryKey: ["audit", params],
    queryFn: () => getAuditEntries(params),
  });
}

export function useAuditFilterOptions() {
  return useQuery({
    queryKey: ["audit", "filters"],
    queryFn: getAuditFilterOptions,
    staleTime: 300_000,
  });
}
