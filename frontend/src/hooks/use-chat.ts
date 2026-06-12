import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";

import {
  deleteConversation,
  emailChatMessage,
  getConversation,
  getConversations,
  sendMessage,
  streamChatMessage,
} from "@/api/chat";
import type { ChatStreamEvent } from "@/api/chat";
import { useOrganizationContext } from "@/hooks/use-organization-context";
import type { ChatRequest } from "@/types/api";

export function useConversations() {
  const { activeOrganization } = useOrganizationContext();

  return useQuery({
    queryKey: ["conversations", activeOrganization?.id],
    queryFn: getConversations,
    enabled: !!activeOrganization,
  });
}

export function useConversation(conversationId: string | null) {
  const { activeOrganization } = useOrganizationContext();

  return useQuery({
    queryKey: ["conversation", conversationId, activeOrganization?.id],
    queryFn: () => getConversation(conversationId!),
    enabled: !!conversationId && !!activeOrganization,
  });
}

export function useSendMessage() {
  const queryClient = useQueryClient();
  const { activeOrganization } = useOrganizationContext();

  return useMutation({
    mutationFn: (payload: ChatRequest) => sendMessage(payload),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({
        queryKey: ["conversations", activeOrganization?.id],
      });
      void queryClient.invalidateQueries({
        queryKey: ["conversation", data.conversation_id, activeOrganization?.id],
      });
    },
  });
}

export interface ChatStreamHandlers {
  onMetadata: (event: Extract<ChatStreamEvent, { event: "metadata" }>) => void;
  onDelta: (content: string) => void;
  onDone: (event: Extract<ChatStreamEvent, { event: "done" }>) => void;
  onError: (message: string) => void;
}

export function useStreamMessage() {
  const queryClient = useQueryClient();
  const { activeOrganization } = useOrganizationContext();
  const abortRef = useRef<AbortController | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const send = useCallback(
    async (payload: ChatRequest, handlers: ChatStreamHandlers) => {
      cancel();
      const controller = new AbortController();
      abortRef.current = controller;
      setIsStreaming(true);

      let conversationId: string | null = null;
      let finished = false;
      try {
        for await (const event of streamChatMessage(payload, controller.signal)) {
          if (event.event === "metadata") {
            conversationId = event.conversation_id;
            handlers.onMetadata(event);
          } else if (event.event === "delta") {
            handlers.onDelta(event.content);
          } else if (event.event === "done") {
            finished = true;
            handlers.onDone(event);
            void queryClient.invalidateQueries({
              queryKey: ["conversations", activeOrganization?.id],
            });
            if (conversationId) {
              void queryClient.invalidateQueries({
                queryKey: ["conversation", conversationId, activeOrganization?.id],
              });
            }
          } else if (event.event === "error") {
            finished = true;
            handlers.onError(event.message);
          }
        }
        // The connection dropped mid-generation: no done/error frame arrived.
        if (!finished && !controller.signal.aborted) {
          handlers.onError("The connection was interrupted before the response finished.");
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          handlers.onError(err instanceof Error ? err.message : "Stream failed");
        }
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
        setIsStreaming(false);
      }
    },
    [cancel, queryClient, activeOrganization?.id],
  );

  return { send, cancel, isStreaming };
}

export function useEmailChatMessage() {
  return useMutation({
    mutationFn: emailChatMessage,
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();
  const { activeOrganization } = useOrganizationContext();

  return useMutation({
    mutationFn: deleteConversation,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["conversations", activeOrganization?.id],
      });
    },
  });
}
