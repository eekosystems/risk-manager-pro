import { useCallback, useEffect, useState } from "react";

import { useConversation, useSendMessage } from "@/hooks/use-chat";
import { useUploadDocument } from "@/hooks/use-documents";
import type { ChatMessage, FunctionType } from "@/types/api";

import { useToast } from "@/components/ui/toast";
import { ChatInput } from "./chat-input";
import { MessageList } from "./message-list";

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "Welcome to Risk Manager Pro. I'm your AI-powered aviation safety assistant, " +
    "ready to help you develop Preliminary Hazard Lists, Safety Risk Assessments, " +
    "and System Analyses. Select a function from the sidebar or ask me anything " +
    "about aviation safety.",
  citations: null,
  created_at: new Date().toISOString(),
};

interface ChatPageProps {
  activeFunction: FunctionType;
  conversationId: string | null;
  setConversationId: (id: string | null) => void;
}

export function ChatPage({
  activeFunction,
  conversationId,
  setConversationId,
}: ChatPageProps) {
  const [localMessages, setLocalMessages] = useState<ChatMessage[]>([
    WELCOME_MESSAGE,
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const { addToast } = useToast();

  const { data: conversation } = useConversation(conversationId);
  const sendMessageMutation = useSendMessage();
  const uploadDocumentMutation = useUploadDocument();

  useEffect(() => {
    if (conversation?.messages) {
      setLocalMessages(conversation.messages);
    }
  }, [conversation]);

  useEffect(() => {
    if (!conversationId) {
      setLocalMessages([WELCOME_MESSAGE]);
    }
  }, [conversationId]);

  const handleSend = useCallback(
    (message: string, files: File[]) => {
      for (const file of files) {
        uploadDocumentMutation.mutate(file, {
          onSuccess: () => {
            addToast(`"${file.name}" uploaded successfully`, "success");
          },
          onError: () => {
            addToast(`Failed to upload "${file.name}"`, "error");
          },
        });
      }

      if (!message) return;

      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: message,
        citations: null,
        created_at: new Date().toISOString(),
      };

      setLocalMessages((prev) => [...prev, userMsg]);
      setIsTyping(true);

      sendMessageMutation.mutate(
        {
          message,
          conversation_id: conversationId,
          function_type: activeFunction,
        },
        {
          onSuccess: (data) => {
            setIsTyping(false);
            setConversationId(data.conversation_id);
            setLocalMessages((prev) => [...prev, data.message]);
          },
          onError: () => {
            setIsTyping(false);
            addToast("Failed to send message. Please try again.", "error");
            setLocalMessages((prev) => [
              ...prev,
              {
                id: `error-${Date.now()}`,
                role: "assistant",
                content:
                  "I'm sorry, I encountered an error processing your request. Please try again.",
                citations: null,
                created_at: new Date().toISOString(),
              },
            ]);
          },
        },
      );
    },
    [
      conversationId,
      activeFunction,
      sendMessageMutation,
      uploadDocumentMutation,
      setConversationId,
      addToast,
    ],
  );

  return (
    <>
      <MessageList messages={localMessages} isTyping={isTyping} />
      <ChatInput
        onSend={handleSend}
        disabled={sendMessageMutation.isPending}
      />
    </>
  );
}
