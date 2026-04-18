import { apiClient } from "@/lib/api-client";
import type { DataResponse } from "@/types/api";

export interface SharePointAirportList {
  airports: string[];
}

export interface SharePointRiskRow {
  airport_identifier: string;
  hazard: string;
  severity: number;
  likelihood: string;
  risk_level: string;
  source_file: string;
  source_url: string | null;
}

export interface SharePointParseNote {
  airport_identifier: string;
  source_file: string;
  message: string;
}

export type RiskOutcomeScanStatus = "idle" | "scanning" | "ready";

export interface RiskOutcomeSummary {
  airports: string[];
  risks: SharePointRiskRow[];
  notes: SharePointParseNote[];
  generated_at: number;
  status: RiskOutcomeScanStatus;
  scanned: number;
  total: number;
  last_scan_completed_at: number | null;
}

export async function listSharePointAirports(): Promise<string[]> {
  const response = await apiClient.get<DataResponse<SharePointAirportList>>(
    "/sharepoint/airports",
  );
  return response.data.data.airports;
}

export async function getRiskOutcomeSummary(
  refresh = false,
): Promise<RiskOutcomeSummary> {
  const response = await apiClient.get<DataResponse<RiskOutcomeSummary>>(
    "/sharepoint/risk-outcome-summary",
    { params: refresh ? { refresh: true } : {} },
  );
  return response.data.data;
}
