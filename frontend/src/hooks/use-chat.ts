import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteConversation,
  getConversation,
  getConversations,
  sendMessage,
} from "@/api/chat";
import { useOrganizationContext } from "@/context/organization-context";
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
