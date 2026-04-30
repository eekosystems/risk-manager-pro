import axios from "axios";
import { useCallback, useEffect, useMemo, useState } from "react";

import { getDocumentById } from "@/api/documents";
import { FUNCTIONS } from "@/constants/functions";
import { useConversation, useEmailChatMessage, useSendMessage } from "@/hooks/use-chat";
import { useUploadDocument } from "@/hooks/use-documents";
import { useToast } from "@/hooks/use-toast";
import { logger } from "@/lib/logger";
import type { ChatMessage, FunctionType } from "@/types/api";

import { ChatInput } from "./chat-input";
import { EmailChatModal } from "./email-chat-modal";
import { MessageList } from "./message-list";

const WELCOME_MESSAGES: Record<FunctionType, string> = {
  phl:
    "You're now in **Hazard Assessment** mode. I'll help you systematically " +
    "identify and assess potential hazards arising from system changes, new " +
    "operations, construction projects, or modified procedures. Describe the " +
    "system or change, or upload a change document (e.g., Construction Safety " +
    "and Phasing Plan (CSPP), operational change order, or system modification " +
    "notice) that you'd like to analyze, and I'll walk you through it " +
    "conversationally.\n\n" +
    "To get started, I can help you with:\n\n" +
    "- Generating a Preliminary Hazard List (PHL) from a described or uploaded system change\n" +
    "- Categorizing hazards as Technical, Human, Organizational, or Environmental\n" +
    "- Providing initial likelihood and severity screening for each identified hazard\n" +
    "- Flagging any hazards that may require a full Safety Risk Assessment (SRA)\n\n" +
    "All outputs are decision-support tools and require Safety Manager/SMS Manager " +
    "or Accountable Executive review before implementation.",
  sra:
    "You're now in **Safety Risk Assessment (SRA)** mode. I'll guide you through " +
    "a structured risk evaluation following FAA Part 139 SMS regulatory guidance " +
    "by default — if you'd like to use different evaluation criteria (e.g., ICAO, " +
    "IATA, or a custom framework), just let me know before we begin. Describe the " +
    "hazard you'd like to assess or upload a hazard document or Preliminary Hazard " +
    "List (PHL) and I'll walk you through it conversationally.\n\n" +
    "To get started, I can help you with:\n\n" +
    "- Assigning likelihood and severity scores using your airport-specific or FAA 5×5 risk matrix\n" +
    "- Calculating initial and residual risk scores with before/after comparison\n" +
    "- Evaluating proposed controls using the hierarchy of controls (Eliminate → Substitute → Engineer → Administrative → PPE)\n" +
    "- Determining ALARP status and whether Accountable Executive acceptance is required\n" +
    "- Flagging High/Extreme risks for mandatory human review and escalation\n\n" +
    "All outputs are decision-support tools and require Safety Manager/SMS Manager " +
    "or Accountable Executive review and approval before implementation.",
  system:
    "You're now in **System Analysis** mode. I'll help you define your system " +
    "and/or analyze system changes, evaluate negative safety trends/data, and " +
    "identify dependencies across your operational systems. Describe the system " +
    "or change, or upload a change document that you'd like to analyze, and I'll " +
    "assist with a structured breakdown.\n\n" +
    "To get started, I can help you with:\n\n" +
    "- Defining or describing a new or existing operational system\n" +
    "- Analyzing a proposed system change and its safety impacts\n" +
    "- Evaluating negative safety outcomes, lagging-indicator spikes, or adverse trends\n" +
    "- Identifying system dependencies and potential failure points\n\n" +
    "All outputs are decision-support tools and require Safety Manager/SMS Manager " +
    "or Accountable Executive review before implementation.",
  general:
    "Welcome to Risk Manager Pro. I'm your AI-powered aviation safety assistant, " +
    "ready to help with any questions about aviation safety, regulatory compliance, " +
    "or your indexed documentation. Select a core function from the sidebar to focus " +
    "on a specific workflow, or ask me anything.",
  risk_register:
    "You're now in **Risk Register** mode. I'll walk you through adding or updating " +
    "a hazard in your Risk Register step by step — hazard description, worst credible " +
    "outcome(s), operational domain, hazard category, risk scoring, existing controls, " +
    "and mitigation actions. Tell me the organization you're working on and describe " +
    "the hazard you'd like to record or upload a hazard report or SRA output and I'll " +
    "extract the relevant information conversationally.\n\n" +
    "To get started, I can help you with:\n\n" +
    "- Recording a new hazard with full classification (Technical, Human, Organizational, or Environmental)\n" +
    "- Assigning and documenting initial and residual risk scores against your organization-specific or FAA 5×5 risk matrix\n" +
    "- Classifying the hazard entry as a Lagging, Leading, or Predictive indicator\n" +
    "- Linking existing controls and mitigation actions with assigned owners and due dates\n" +
    "- Flagging entries that require Accountable Executive review or a full Safety Risk Assessment (SRA)\n\n" +
    "All outputs are decision-support tools and require Safety Manager/SMS Manager " +
    "or Accountable Executive review and approval before the record is finalized.",
};

function buildRiskRegisterSeed(assistantContent: string): string {
  const trimmed = assistantContent.trim();
  return (
    "Please extract the hazard(s) from the analysis below and add them to the " +
    "Risk Register. Ask me any follow-up questions you need (airport, operational " +
    "domain, existing controls, etc.) before saving.\n\n" +
    "--- Analysis from prior chat ---\n\n" +
    trimmed
  );
}

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
  onStartChat: (fn: FunctionType, seed?: string) => void;
  onFunctionRouted: (fn: FunctionType) => void;
  pendingInputSeed: string | null;
  clearPendingInputSeed: () => void;
}

export function ChatPage({
  activeFunction,
  conversationId,
  setConversationId,
  onStartChat,
  onFunctionRouted,
  pendingInputSeed,
  clearPendingInputSeed,
}: ChatPageProps) {
  const welcomeMessage = useMemo(() => buildWelcomeMessage(activeFunction), [activeFunction]);
  const [localMessages, setLocalMessages] = useState<ChatMessage[]>([
    welcomeMessage,
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const [emailTargetContent, setEmailTargetContent] = useState<string | null>(null);
  const { addToast } = useToast();
  const emailChatMutation = useEmailChatMessage();

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
    async (message: string, files: File[]) => {
      // When the user attaches files, the chat query has to wait for the
      // document(s) to finish indexing into Azure AI Search — otherwise the
      // RAG retrieval finds nothing about the just-uploaded file and the AI
      // returns a generic "I don't have information" reply. The previous
      // implementation fired uploads in the background while sending the
      // chat message immediately, which is exactly the race that caused
      // empty / no-output responses.
      //
      // Flow now:
      //   1. await each upload → returns a document with status="uploaded"
      //   2. poll GET /documents/{id} every 1.5s until status="indexed",
      //      capped at 90s so a stuck/slow doc can't lock the user out
      //   3. then send the chat message
      const uploadedIds: string[] = [];
      if (files.length > 0) {
        addToast(
          files.length === 1
            ? `Indexing "${files[0]?.name}"…`
            : `Indexing ${files.length} files…`,
          "info",
        );
        for (const file of files) {
          try {
            const doc = await uploadDocumentMutation.mutateAsync({ file });
            uploadedIds.push(doc.id);
          } catch {
            addToast(`Failed to upload "${file.name}"`, "error");
          }
        }

        const POLL_INTERVAL_MS = 1500;
        const POLL_TIMEOUT_MS = 90_000;
        const start = Date.now();
        const stillPending = new Set(uploadedIds);
        while (stillPending.size > 0 && Date.now() - start < POLL_TIMEOUT_MS) {
          await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
          for (const id of [...stillPending]) {
            try {
              const doc = await getDocumentById(id);
              if (doc.status === "indexed") {
                stillPending.delete(id);
              } else if (doc.status === "failed") {
                stillPending.delete(id);
                addToast(`Indexing failed for "${doc.filename}"`, "error");
              }
            } catch {
              // Transient fetch error — keep polling until the timeout.
            }
          }
        }
        if (stillPending.size > 0) {
          addToast(
            "Indexing is taking longer than expected — sending your message now; the file may not be searchable yet.",
            "warning",
          );
        }
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
            logger.warn("[chat] sendMessage success", {
              conversation_id: data.conversation_id,
              message_id: data.message.id,
              content_length: data.message.content?.length ?? 0,
              content_preview: data.message.content?.slice(0, 200) ?? null,
              citations_count: data.message.citations?.length ?? 0,
              routed_function_type: data.routed_function_type,
            });
            setLocalMessages((prev) => [...prev, data.message]);
            if (
              data.routed_function_type &&
              data.routed_function_type !== activeFunction
            ) {
              onFunctionRouted(data.routed_function_type);
              const target = FUNCTIONS.find(
                (f) => f.id === data.routed_function_type,
              );
              addToast(
                `Switched to ${target?.name ?? data.routed_function_type}`,
                "info",
              );
            }
          },
          onError: (error) => {
            setIsTyping(false);
            if (axios.isAxiosError(error)) {
              logger.error("[chat] sendMessage failed", {
                status: error.response?.status,
                statusText: error.response?.statusText,
                data: error.response?.data,
                code: error.code,
                message: error.message,
                url: error.config?.url,
                timeout: error.config?.timeout,
              });
            } else {
              logger.error("[chat] sendMessage failed", error);
            }
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
      onFunctionRouted,
      addToast,
    ],
  );

  const handleSaveAsRisk = useCallback(
    (messageContent: string) => {
      const seed = buildRiskRegisterSeed(messageContent);
      onStartChat("risk_register", seed);
      addToast(
        "Carried the analysis into Risk Register mode — review and send to save.",
        "success",
      );
    },
    [onStartChat, addToast],
  );

  const handleEmail = useCallback((content: string) => {
    setEmailTargetContent(content);
  }, []);

  // Feature flag — flip to `true` to re-enable the "Send Email" button on
  // every assistant message in the chat output. Backend email delivery is
  // currently unreliable, so the action is hidden in the UI for now. All
  // wiring (handleEmail, emailChatMutation, EmailChatModal) is preserved.
  const EMAIL_ON_CHAT_OUTPUT_ENABLED = false;

  const handleSendEmail = useCallback(
    (payload: { to: string; subject: string; content: string }) => {
      emailChatMutation.mutate(payload, {
        onSuccess: () => {
          setEmailTargetContent(null);
          addToast(`Email sent to ${payload.to}`, "success");
        },
        onError: () => {
          addToast("Failed to send email", "error");
        },
      });
    },
    [emailChatMutation, addToast],
  );

  const handleCopied = useCallback(() => {
    addToast("Copied to clipboard", "success");
  }, [addToast]);

  const handleCopyFailed = useCallback(() => {
    addToast("Copy failed — select the text manually", "error");
  }, [addToast]);

  return (
    <>
      <MessageList
        messages={localMessages}
        isTyping={isTyping}
        onSaveAsRisk={handleSaveAsRisk}
        {...(EMAIL_ON_CHAT_OUTPUT_ENABLED ? { onEmail: handleEmail } : {})}
        onCopied={handleCopied}
        onCopyFailed={handleCopyFailed}
      />
      <ChatInput
        onSend={handleSend}
        disabled={sendMessageMutation.isPending}
        seedValue={pendingInputSeed}
        onSeedConsumed={clearPendingInputSeed}
        activeFunction={activeFunction}
      />
      {emailTargetContent !== null && (
        <EmailChatModal
          content={emailTargetContent}
          onClose={() => setEmailTargetContent(null)}
          onSubmit={handleSendEmail}
          isPending={emailChatMutation.isPending}
        />
      )}
    </>
  );
}
