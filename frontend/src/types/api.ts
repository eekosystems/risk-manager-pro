export type FunctionType = "phl" | "sra" | "system" | "general" | "risk_register";
export type MessageRole = "user" | "assistant" | "system";
export type DocumentStatus = "uploaded" | "processing" | "indexed" | "failed";
export type SourceType = "client" | "faa" | "icao" | "easa" | "nasa_asrs" | "internal";
export type MembershipRole = "org_admin" | "analyst" | "viewer";
export type InvitationStatus = "active" | "invited" | "provisioned";
export type OrganizationStatus = "active" | "suspended" | "archived";

export interface Citation {
  source: string;
  source_type: SourceType;
  section: string | null;
  content: string;
  chunk_id: string | null;
  rank: number | null;
  match_tier: string | null;
}

export interface OrganizationSummary {
  id: string;
  name: string;
  slug: string;
  status: OrganizationStatus;
  is_platform: boolean;
}

export interface OrganizationDetail extends OrganizationSummary {
  created_at: string;
  updated_at: string;
}

export interface OrganizationMember {
  id: string;
  user_id: string;
  organization_id: string;
  role: MembershipRole;
  is_active: boolean;
  email: string;
  display_name: string;
  invitation_status: InvitationStatus;
  created_at: string;
}

export interface UserOrgMembership {
  organization_id: string;
  organization_name: string;
  role: MembershipRole;
  is_active: boolean;
}

export interface UserProfile {
  id: string;
  email: string;
  display_name: string;
  is_platform_admin: boolean;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
  organizations: UserOrgMembership[];
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  citations: Citation[] | null;
  created_at: string;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string | null;
  function_type: FunctionType;
}

export interface ChatResponse {
  conversation_id: string;
  message: ChatMessage;
  title: string;
}

export interface ConversationListItem {
  id: string;
  title: string;
  function_type: FunctionType;
  updated_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string;
  function_type: FunctionType;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
}

export interface DocumentItem {
  id: string;
  filename: string;
  folder_path: string | null;
  content_type: string;
  size_bytes: number;
  status: DocumentStatus;
  source_type: SourceType;
  created_at: string;
}

export interface DocumentDetail extends DocumentItem {
  chunk_count: number;
  error_message: string | null;
  updated_at: string;
}

export interface DataResponse<T> {
  data: T;
  meta: { request_id: string };
}

export interface PaginatedResponse<T> {
  data: T[];
  meta: {
    request_id: string;
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
  };
}

export interface ErrorResponse {
  error: { code: string; message: string };
}

// --- Risk Register Types ---

export type RiskStatus = "open" | "mitigating" | "closed" | "accepted";
export type MitigationStatus = "pending" | "in_progress" | "completed" | "cancelled";

export type OperationalDomain =
  | "movement_area"
  | "non_movement_area"
  | "ramp"
  | "terminal"
  | "landside"
  | "user_defined";
export type HazardCategory5M = "human" | "machine" | "medium" | "mission" | "management";
export type HazardCategoryICAO = "technical" | "human" | "organizational" | "environmental";
export type RiskMatrixApplied = "airport_specific" | "faa_5x5" | "conservative_default";
export type RecordStatus =
  | "open"
  | "in_progress"
  | "pending_assessment"
  | "closed"
  | "monitoring";
export type ValidationStatus = "rmp_validated" | "user_reported" | "pending";
export type RecordSource =
  | "rmp_sp1"
  | "rmp_sp2"
  | "rmp_sp3"
  | "rmp_sp4"
  | "manual_entry"
  | "fg_push"
  | "client_push";
export type SyncStatus = "fg_only" | "client_only" | "dual_in_sync" | "dual_pending";

export interface RiskEntryListItem {
  id: string;
  title: string;
  hazard: string;
  severity: number;
  likelihood: string;
  risk_level: string;
  status: RiskStatus;
  function_type: string;
  airport_identifier: string | null;
  operational_domain: OperationalDomain | null;
  hazard_category_5m: HazardCategory5M | null;
  record_status: RecordStatus;
  validation_status: ValidationStatus;
  source: RecordSource;
  created_at: string;
  updated_at: string;
}

export interface MitigationItem {
  id: string;
  risk_entry_id: string;
  title: string;
  description: string;
  assignee: string | null;
  due_date: string | null;
  verification_method: string | null;
  status: MitigationStatus;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RiskEntryDetail {
  id: string;
  organization_id: string;
  created_by: string;
  title: string;
  description: string;
  hazard: string;
  severity: number;
  likelihood: string;
  risk_level: string;
  status: RiskStatus;
  function_type: string;
  conversation_id: string | null;
  notes: string | null;
  airport_identifier: string | null;
  potential_credible_outcome: string | null;
  operational_domain: OperationalDomain | null;
  sub_location: string | null;
  hazard_category_5m: HazardCategory5M | null;
  hazard_category_icao: HazardCategoryICAO | null;
  risk_matrix_applied: RiskMatrixApplied;
  existing_controls: string | null;
  residual_risk_level: string | null;
  record_status: RecordStatus;
  validation_status: ValidationStatus;
  source: RecordSource;
  sync_status: SyncStatus;
  acm_cross_reference: string | null;
  created_at: string;
  updated_at: string;
  mitigations: MitigationItem[];
}

export interface CreateRiskEntryRequest {
  title: string;
  description: string;
  hazard: string;
  severity: number;
  likelihood: string;
  function_type?: string;
  conversation_id?: string | null;
  notes?: string | null;
  airport_identifier?: string | null;
  potential_credible_outcome?: string | null;
  operational_domain?: OperationalDomain | null;
  sub_location?: string | null;
  hazard_category_5m?: HazardCategory5M | null;
  hazard_category_icao?: HazardCategoryICAO | null;
  risk_matrix_applied?: RiskMatrixApplied;
  existing_controls?: string | null;
  residual_risk_level?: string | null;
  record_status?: RecordStatus;
  validation_status?: ValidationStatus;
  source?: RecordSource;
  acm_cross_reference?: string | null;
}

export interface UpdateRiskEntryRequest {
  title?: string | null;
  description?: string | null;
  hazard?: string | null;
  severity?: number | null;
  likelihood?: string | null;
  status?: RiskStatus | null;
  notes?: string | null;
  airport_identifier?: string | null;
  potential_credible_outcome?: string | null;
  operational_domain?: OperationalDomain | null;
  sub_location?: string | null;
  hazard_category_5m?: HazardCategory5M | null;
  hazard_category_icao?: HazardCategoryICAO | null;
  risk_matrix_applied?: RiskMatrixApplied | null;
  existing_controls?: string | null;
  residual_risk_level?: string | null;
  record_status?: RecordStatus | null;
  validation_status?: ValidationStatus | null;
  acm_cross_reference?: string | null;
}

export interface CreateMitigationRequest {
  title: string;
  description: string;
  assignee?: string | null;
  due_date?: string | null;
  verification_method?: string | null;
}

export interface UpdateMitigationRequest {
  title?: string | null;
  description?: string | null;
  assignee?: string | null;
  due_date?: string | null;
  verification_method?: string | null;
  status?: MitigationStatus | null;
}

export interface SubLocation {
  id: string;
  airport_identifier: string;
  name: string;
  created_at: string;
}

// --- Analytics Dashboard Types ---

export interface RiskKPIs {
  total_risks: number;
  open_risks: number;
  high_count: number;
  overdue_mitigations: number;
  avg_days_to_close: number | null;
}

export interface RiskLevelTimeSeries {
  month: string;
  low: number;
  medium: number;
  high: number;
}

export interface RiskStatusBreakdownItem {
  status: string;
  count: number;
}

export interface RisksByFunctionTypeItem {
  function_type: string;
  count: number;
}

export interface MitigationPerformance {
  total_mitigations: number;
  completed_count: number;
  overdue_count: number;
  completion_rate: number;
  avg_days_to_complete: number | null;
}

export interface RiskPositionItem {
  likelihood: string;
  severity: number;
  count: number;
}

export interface DashboardData {
  kpis: RiskKPIs;
  risk_level_over_time: RiskLevelTimeSeries[];
  status_breakdown: RiskStatusBreakdownItem[];
  by_function_type: RisksByFunctionTypeItem[];
  mitigation_performance: MitigationPerformance;
  risk_positions: RiskPositionItem[];
}

export interface ActivityEntry {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  outcome: string;
  timestamp: string;
  user_id: string;
}

// --- Audit Log Types ---

export interface AuditEntry {
  id: string;
  timestamp: string;
  user_id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  ip_address: string;
  correlation_id: string;
  outcome: string;
  organization_id: string | null;
}

export interface AuditFilterOptions {
  actions: string[];
  resource_types: string[];
  outcomes: string[];
}

// --- Notification Types ---

export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  body: string;
  resource_type: string;
  resource_id: string | null;
  is_read: boolean;
  created_at: string;
  triggered_by_user_id: string;
}

export interface UnreadCount {
  count: number;
}
