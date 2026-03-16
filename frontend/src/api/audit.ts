import { apiClient } from "@/lib/api-client";
import type {
  AuditEntry,
  AuditFilterOptions,
  DataResponse,
  PaginatedResponse,
} from "@/types/api";

export interface GetAuditParams {
  skip?: number;
  limit?: number;
  action?: string;
  resource_type?: string;
  outcome?: string;
  user_id?: string;
  date_from?: string;
  date_to?: string;
}

export async function getAuditEntries(
  params: GetAuditParams = {},
): Promise<{ data: AuditEntry[]; total: number; total_pages: number }> {
  const response = await apiClient.get<PaginatedResponse<AuditEntry>>(
    "/audit",
    { params },
  );
  return {
    data: response.data.data,
    total: response.data.meta.total,
    total_pages: response.data.meta.total_pages,
  };
}

export async function getAuditFilterOptions(): Promise<AuditFilterOptions> {
  const response = await apiClient.get<DataResponse<AuditFilterOptions>>(
    "/audit/filters",
  );
  return response.data.data;
}

export async function exportAuditCsv(
  params: Omit<GetAuditParams, "skip" | "limit"> = {},
): Promise<void> {
  const response = await apiClient.get("/audit/export", {
    params,
    responseType: "blob",
  });
  const blob = new Blob([response.data as BlobPart], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "audit_log.csv";
  a.click();
  URL.revokeObjectURL(url);
}
