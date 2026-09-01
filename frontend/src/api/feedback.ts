import { apiClient } from "@/lib/api-client";
import type {
  ApplicationGuidance,
  DataResponse,
  FeedbackItem,
  FeedbackRating,
  FeedbackReviewItem,
  FeedbackStatus,
  FunctionType,
  GuidanceScope,
  PaginatedResponse,
} from "@/types/api";

export interface SubmitFeedbackParams {
  conversationId: string;
  messageId: string;
  rating: FeedbackRating;
  comment: string;
}

export async function submitFeedback(
  params: SubmitFeedbackParams,
): Promise<FeedbackItem> {
  const response = await apiClient.post<DataResponse<FeedbackItem>>("/feedback", {
    conversation_id: params.conversationId,
    message_id: params.messageId,
    rating: params.rating,
    comment: params.comment,
  });
  return response.data.data;
}

export interface GetFeedbackParams {
  status?: FeedbackStatus;
  skip?: number;
  limit?: number;
}

export async function getFeedback(
  params: GetFeedbackParams = {},
): Promise<{ data: FeedbackReviewItem[]; total: number }> {
  const response = await apiClient.get<PaginatedResponse<FeedbackReviewItem>>(
    "/feedback",
    { params },
  );
  return { data: response.data.data, total: response.data.meta.total };
}

export interface ReviewFeedbackParams {
  feedbackId: string;
  status: FeedbackStatus;
  reviewNote?: string;
}

export async function reviewFeedback(
  params: ReviewFeedbackParams,
): Promise<FeedbackItem> {
  const response = await apiClient.patch<DataResponse<FeedbackItem>>(
    `/feedback/${params.feedbackId}`,
    { status: params.status, review_note: params.reviewNote ?? null },
  );
  return response.data.data;
}

export interface PromoteFeedbackParams {
  feedbackId: string;
  content: string;
  scope: GuidanceScope;
  functionType?: FunctionType | null;
}

/** Turn a piece of feedback into a rule that shapes every future answer. */
export async function promoteFeedback(
  params: PromoteFeedbackParams,
): Promise<ApplicationGuidance> {
  const response = await apiClient.post<DataResponse<ApplicationGuidance>>(
    `/feedback/${params.feedbackId}/promote`,
    {
      content: params.content,
      scope: params.scope,
      function_type: params.functionType ?? null,
    },
  );
  return response.data.data;
}

// Guidance store

export async function getGuidance(): Promise<ApplicationGuidance[]> {
  const response =
    await apiClient.get<DataResponse<ApplicationGuidance[]>>("/guidance");
  return response.data.data;
}

export interface CreateGuidanceParams {
  content: string;
  scope: GuidanceScope;
  organizationId?: string | null;
  functionType?: FunctionType | null;
}

export async function createGuidance(
  params: CreateGuidanceParams,
): Promise<ApplicationGuidance> {
  const response = await apiClient.post<DataResponse<ApplicationGuidance>>(
    "/guidance",
    {
      content: params.content,
      scope: params.scope,
      organization_id: params.organizationId ?? null,
      function_type: params.functionType ?? null,
    },
  );
  return response.data.data;
}

export interface UpdateGuidanceParams {
  guidanceId: string;
  content?: string;
  isActive?: boolean;
}

export async function updateGuidance(
  params: UpdateGuidanceParams,
): Promise<ApplicationGuidance> {
  const body: Record<string, unknown> = {};
  if (params.content !== undefined) body.content = params.content;
  if (params.isActive !== undefined) body.is_active = params.isActive;
  const response = await apiClient.patch<DataResponse<ApplicationGuidance>>(
    `/guidance/${params.guidanceId}`,
    body,
  );
  return response.data.data;
}

export async function deleteGuidance(guidanceId: string): Promise<void> {
  await apiClient.delete(`/guidance/${guidanceId}`);
}
