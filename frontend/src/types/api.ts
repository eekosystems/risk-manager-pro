export type FunctionType = "phl" | "sra" | "system" | "general";
export type MessageRole = "user" | "assistant" | "system";
export type DocumentStatus = "uploaded" | "processing" | "indexed" | "failed";
export type MembershipRole = "org_admin" | "analyst" | "viewer";
export type OrganizationStatus = "active" | "suspended" | "archived";

export interface Citation {
  source: string;
  section: string | null;
  content: string;
  score: number | null;
  chunk_id: string | null;
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
  content_type: string;
  size_bytes: number;
  status: DocumentStatus;
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
