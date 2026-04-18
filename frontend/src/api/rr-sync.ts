import { apiClient } from "@/lib/api-client";
import type { DataResponse } from "@/types/api";

// --- Types ---

export type PendingChangeType = "create" | "update" | "close";
export type PendingChangeDirection = "client_to_fg" | "fg_to_client";
export type PendingChangeStatus = "pending" | "accepted" | "rejected";
export type ACPDecision =
  | "pending"
  | "accepted_new_record"
  | "accepted_linked"
  | "accepted_monitor"
  | "dismissed";
export type ACPIntelligenceSource =
  | "faa_incident"
  | "nasa_asrs"
  | "notam"
  | "regulatory_action"
  | "safety_news"
  | "manual";
export type ClosureApprovalStatus = "pending" | "approved" | "rejected";

export interface PendingSyncChange {
  id: string;
  link_id: string | null;
  source_risk_entry_id: string;
  source_organization_id: string;
  target_organization_id: string;
  change_type: PendingChangeType;
  direction: PendingChangeDirection;
  status: PendingChangeStatus;
  diff_json: Record<string, unknown>;
  initiator_user_id: string;
  reviewer_user_id: string | null;
  review_note: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface ACPRecord {
  id: string;
  organization_id: string;
  airport_identifier: string;
  system_profile: string | null;
  known_risk_factors: string | null;
  stakeholder_notes: string | null;
  operational_impact_history: string | null;
  extra_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ACPIntelligenceItem {
  id: string;
  acp_id: string;
  airport_identifier: string;
  source: ACPIntelligenceSource;
  headline: string;
  summary: string | null;
  occurred_at: string | null;
  external_url: string | null;
  external_ref: string | null;
  decision: ACPDecision;
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string | null;
  linked_risk_entry_id: string | null;
  created_at: string;
}

export interface ClosureApproval {
  id: string;
  risk_entry_id: string;
  requested_by: string;
  request_note: string | null;
  status: ClosureApprovalStatus;
  approver_user_id: string | null;
  approval_note: string | null;
  requested_at: string;
  resolved_at: string | null;
}

export interface PortfolioRiskRow {
  id: string;
  organization_id: string;
  organization_name: string;
  airport_identifier: string | null;
  title: string;
  hazard: string;
  severity: number;
  likelihood: string;
  risk_level: string;
  record_status: string;
  validation_status: string;
  source: string;
  created_at: string;
  updated_at: string;
}

// --- Sync queue ---

export async function listPendingSyncChanges(
  status: PendingChangeStatus = "pending",
): Promise<PendingSyncChange[]> {
  const response = await apiClient.get<DataResponse<PendingSyncChange[]>>(
    "/rr/sync-queue",
    { params: { status } },
  );
  return response.data.data;
}

export async function acceptPendingChange(
  pendingId: string,
  note?: string,
): Promise<PendingSyncChange> {
  const response = await apiClient.post<DataResponse<PendingSyncChange>>(
    `/rr/sync-queue/${pendingId}/accept`,
    { note: note ?? null },
  );
  return response.data.data;
}

export async function rejectPendingChange(
  pendingId: string,
  note?: string,
): Promise<PendingSyncChange> {
  const response = await apiClient.post<DataResponse<PendingSyncChange>>(
    `/rr/sync-queue/${pendingId}/reject`,
    { note: note ?? null },
  );
  return response.data.data;
}

// --- ACP ---

export async function getACP(airportIdentifier: string): Promise<ACPRecord> {
  const response = await apiClient.get<DataResponse<ACPRecord>>(
    `/rr/acp/${encodeURIComponent(airportIdentifier)}`,
  );
  return response.data.data;
}

export async function updateACP(
  acpId: string,
  payload: Partial<
    Pick<
      ACPRecord,
      | "system_profile"
      | "known_risk_factors"
      | "stakeholder_notes"
      | "operational_impact_history"
    >
  >,
): Promise<ACPRecord> {
  const response = await apiClient.patch<DataResponse<ACPRecord>>(
    `/rr/acp/${acpId}`,
    payload,
  );
  return response.data.data;
}

export interface CreateACPIntelligenceItem {
  airport_identifier: string;
  source: ACPIntelligenceSource;
  headline: string;
  summary?: string | null;
  occurred_at?: string | null;
  external_url?: string | null;
  external_ref?: string | null;
  raw_payload?: Record<string, unknown> | null;
}

export async function createIntelligenceItem(
  payload: CreateACPIntelligenceItem,
): Promise<ACPIntelligenceItem> {
  const response = await apiClient.post<DataResponse<ACPIntelligenceItem>>(
    "/rr/acp/intelligence",
    payload,
  );
  return response.data.data;
}

export async function listIntelligenceItems(params?: {
  airport_identifier?: string;
  decision?: ACPDecision;
}): Promise<ACPIntelligenceItem[]> {
  const response = await apiClient.get<DataResponse<ACPIntelligenceItem[]>>(
    "/rr/acp/intelligence",
    { params },
  );
  return response.data.data;
}

export async function decideIntelligenceItem(
  itemId: string,
  decision: ACPDecision,
  note?: string,
  linkedRiskEntryId?: string,
): Promise<ACPIntelligenceItem> {
  const response = await apiClient.post<DataResponse<ACPIntelligenceItem>>(
    `/rr/acp/intelligence/${itemId}/decide`,
    {
      decision,
      note: note ?? null,
      linked_risk_entry_id: linkedRiskEntryId ?? null,
    },
  );
  return response.data.data;
}

// --- Closure approvals ---

export async function requestClosureApproval(
  riskId: string,
  note?: string,
): Promise<ClosureApproval> {
  const response = await apiClient.post<DataResponse<ClosureApproval>>(
    `/rr/closures/${riskId}/request`,
    { note: note ?? null },
  );
  return response.data.data;
}

export async function decideClosureApproval(
  approvalId: string,
  approve: boolean,
  note?: string,
): Promise<ClosureApproval> {
  const response = await apiClient.post<DataResponse<ClosureApproval>>(
    `/rr/closures/${approvalId}/decide`,
    { approve, note: note ?? null },
  );
  return response.data.data;
}

// --- Portfolio (platform admin only) ---

export async function getPortfolio(params?: {
  airport_identifier?: string;
  risk_level?: string;
  limit?: number;
}): Promise<PortfolioRiskRow[]> {
  const response = await apiClient.get<DataResponse<PortfolioRiskRow[]>>(
    "/rr/portfolio",
    { params },
  );
  return response.data.data;
}
