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
import { useOrganizationContext } from "@/hooks/use-organization-context";
import type { ChatRequest, Citation } from "@/types/api";

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

interface StreamState {
  streaming: boolean;
  content: string;
  conversationId: string | null;
  error: string | null;
  citations: Citation[] | null;
}

export function useStreamMessage() {
  const queryClient = useQueryClient();
  const { activeOrganization } = useOrganizationContext();
  const abortRef = useRef<AbortController | null>(null);
  const [state, setState] = useState<StreamState>({
    streaming: false,
    content: "",
    conversationId: null,
    error: null,
    citations: null,
  });

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const start = useCallback(
    async (payload: ChatRequest) => {
      cancel();
      const controller = new AbortController();
      abortRef.current = controller;
      setState({
        streaming: true,
        content: "",
        conversationId: null,
        error: null,
        citations: null,
      });

      try {
        for await (const event of streamChatMessage(payload, controller.signal)) {
          if (event.event === "metadata") {
            setState((s) => ({ ...s, conversationId: event.conversation_id }));
          } else if (event.event === "delta") {
            setState((s) => ({ ...s, content: s.content + event.content }));
          } else if (event.event === "done") {
            setState((s) => ({
              ...s,
              streaming: false,
              citations: event.citations,
            }));
            void queryClient.invalidateQueries({
              queryKey: ["conversations", activeOrganization?.id],
            });
          } else if (event.event === "error") {
            setState((s) => ({ ...s, streaming: false, error: event.message }));
          }
        }
      } catch (err) {
        setState((s) => ({
          ...s,
          streaming: false,
          error: err instanceof Error ? err.message : "Stream failed",
        }));
      } finally {
        abortRef.current = null;
      }
    },
    [cancel, queryClient, activeOrganization?.id],
  );

  return { ...state, start, cancel };
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
