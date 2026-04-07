import { useCallback, useEffect, useMemo, useState } from "react";

import { CreateRiskModal } from "@/components/risk-register/create-risk-modal";
import { useConversation, useSendMessage } from "@/hooks/use-chat";
import { useUploadDocument } from "@/hooks/use-documents";
import { useCreateRisk } from "@/hooks/use-risks";
import { useToast } from "@/hooks/use-toast";
import type { ChatMessage, CreateRiskEntryRequest, FunctionType } from "@/types/api";

import { ChatInput } from "./chat-input";
import { MessageList } from "./message-list";

const WELCOME_MESSAGES: Record<FunctionType, string> = {
  phl:
    "You're now in **Preliminary Hazard List (PHL)** mode. I'll help you " +
    "systematically identify potential hazards arising from system changes, " +
    "new operations, or modified procedures. Describe the system or change " +
    "you'd like to analyze, or use the PHL Wizard from the sidebar for a " +
    "step-by-step guided workflow.",
  sra:
    "You're now in **Safety Risk Assessment (SRA)** mode. I'll guide you through " +
    "a structured risk evaluation following AC 150/5200-37A, including severity and " +
    "likelihood scoring, risk acceptance criteria, and mitigation planning. " +
    "Describe the hazard you'd like to assess, or use the SRA Wizard for a " +
    "guided workflow.",
  system:
    "You're now in **System Analysis** mode. I'll help you analyze system changes, " +
    "evaluate their safety impacts, and identify dependencies across your operations. " +
    "Describe the system or change you'd like to analyze and I'll assist with a " +
    "structured breakdown.",
  general:
    "Welcome to Risk Manager Pro. I'm your AI-powered aviation safety assistant, " +
    "ready to help with any questions about aviation safety, regulatory compliance, " +
    "or your indexed documentation. Select a core function from the sidebar to focus " +
    "on a specific workflow, or ask me anything.",
};

function buildWelcomeMessage(functionType: FunctionType): ChatMessage {
  return {
    id: `welcome-${functionType}`,
    role: "assistant",
    content: WELCOME_MESSAGES[functionType],
    citations: null,
    created_at: new Date().toISOString(),
  };
}

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
  const welcomeMessage = useMemo(() => buildWelcomeMessage(activeFunction), [activeFunction]);
  const [localMessages, setLocalMessages] = useState<ChatMessage[]>([
    welcomeMessage,
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const [showRiskModal, setShowRiskModal] = useState(false);
  const { addToast } = useToast();
  const createRiskMutation = useCreateRisk();

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
      setLocalMessages([buildWelcomeMessage(activeFunction)]);
    }
  }, [conversationId, activeFunction]);

  const handleSend = useCallback(
    (message: string, files: File[]) => {
      for (const file of files) {
        uploadDocumentMutation.mutate({ file }, {
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

  const handleSaveAsRisk = useCallback(() => {
    setShowRiskModal(true);
  }, []);

  const handleCreateRisk = useCallback(
    (payload: CreateRiskEntryRequest) => {
      createRiskMutation.mutate(payload, {
        onSuccess: () => {
          setShowRiskModal(false);
          addToast("Risk entry created successfully", "success");
        },
        onError: () => {
          addToast("Failed to create risk entry", "error");
        },
      });
    },
    [createRiskMutation, addToast],
  );

  return (
    <>
      <MessageList
        messages={localMessages}
        isTyping={isTyping}
        onSaveAsRisk={handleSaveAsRisk}
      />
      <ChatInput
        onSend={handleSend}
        disabled={sendMessageMutation.isPending}
      />
      {showRiskModal && (
        <CreateRiskModal
          onClose={() => setShowRiskModal(false)}
          onSubmit={handleCreateRisk}
          isPending={createRiskMutation.isPending}
          defaultFunctionType={activeFunction}
          conversationId={conversationId}
        />
      )}
    </>
  );
}
