import { apiClient, getAuthHeaders } from "@/lib/api-client";
import { env } from "@/config/env";
import type {
  ChatRequest,
  ChatResponse,
  Citation,
  ConversationDetail,
  ConversationListItem,
  DataResponse,
} from "@/types/api";

export type ChatStreamEvent =
  | { event: "metadata"; conversation_id: string; title: string | null }
  | { event: "delta"; content: string }
  | { event: "done"; message_id: string; citations: Citation[] | null }
  | { event: "error"; message: string };

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

export async function* streamChatMessage(
  payload: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const headers = await getAuthHeaders();
  const init: RequestInit = {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
  if (signal) init.signal = signal;
  const response = await fetch(`${env.apiBaseUrl}/chat/stream`, init);

  if (!response.ok || !response.body) {
    throw new Error(`Chat stream failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        for (const line of frame.split("\n")) {
          if (!line.startsWith("data:")) continue;
          const jsonStr = line.slice(5).trim();
          if (!jsonStr) continue;
          try {
            yield JSON.parse(jsonStr) as ChatStreamEvent;
          } catch {
            // malformed frame — skip
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
