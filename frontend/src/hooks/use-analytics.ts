import { useQuery } from "@tanstack/react-query";

import { getDashboard, getRecentActivity } from "@/api/analytics";

export function useDashboard() {
  return useQuery({
    queryKey: ["analytics", "dashboard"],
    queryFn: getDashboard,
    staleTime: 60_000,
    refetchInterval: 300_000,
  });
}

export function useRecentActivity(limit: number = 20) {
  return useQuery({
    queryKey: ["analytics", "activity", limit],
    queryFn: () => getRecentActivity(limit),
    staleTime: 30_000,
    refetchInterval: 120_000,
  });
}
