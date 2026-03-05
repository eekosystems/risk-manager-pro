import { apiClient } from "@/lib/api-client";
import type {
  ChatRequest,
  ChatResponse,
  ConversationDetail,
  ConversationListItem,
  DataResponse,
} from "@/types/api";

export async function sendMessage(
  payload: ChatRequest,
): Promise<ChatResponse> {
  const response =
    await apiClient.post<DataResponse<ChatResponse>>("/chat", payload);
  return response.data.data;
}

export async function getConversations(): Promise<ConversationListItem[]> {
  const response =
    await apiClient.get<DataResponse<ConversationListItem[]>>("/chat/conversations");
  return response.data.data;
}

export async function getConversation(
  conversationId: string,
): Promise<ConversationDetail> {
  const response =
    await apiClient.get<DataResponse<ConversationDetail>>(
      `/chat/conversations/${conversationId}`,
    );
  return response.data.data;
}

export async function deleteConversation(
  conversationId: string,
): Promise<void> {
  await apiClient.delete(`/chat/conversations/${conversationId}`);
}
