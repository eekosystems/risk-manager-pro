import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { search } from "@/api/search";
import { useOrganizationContext } from "@/hooks/use-organization-context";

export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const handle = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(handle);
  }, [value, delayMs]);

  return debounced;
}

export function useSearch(query: string) {
  const { activeOrganization } = useOrganizationContext();
  const trimmed = query.trim();
  const debounced = useDebouncedValue(trimmed, 250);
  const enabled = !!activeOrganization && debounced.length >= 2;

  return useQuery({
    queryKey: ["search", debounced, activeOrganization?.id],
    queryFn: () => search(debounced),
    enabled,
    staleTime: 30_000,
  });
}
