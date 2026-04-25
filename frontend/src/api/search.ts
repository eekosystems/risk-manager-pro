import { apiClient } from "@/lib/api-client";
import type { DataResponse, SearchResults } from "@/types/api";

export async function search(query: string, limit = 10): Promise<SearchResults> {
  const response = await apiClient.get<DataResponse<SearchResults>>("/search", {
    params: { q: query, limit },
  });
  return response.data.data;
}
