import axios from "axios";
import { clsx } from "clsx";
import { ArrowRight, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getDocumentById } from "@/api/documents";
import { FUNCTIONS } from "@/constants/functions";
import { useConversation, useEmailChatMessage, useSendMessage } from "@/hooks/use-chat";
import { useUploadDocument } from "@/hooks/use-documents";
import { useToast } from "@/hooks/use-toast";
import { extractFollowups, type Followup } from "@/lib/followups";
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
  onFunctionRouted: (fn: FunctionType) => void;
  onNavigateRiskRegister: () => void;
  pendingInputSeed: string | null;
  clearPendingInputSeed: () => void;
}

export function ChatPage({
  activeFunction,
  conversationId,
  setConversationId,
  onFunctionRouted,
  onNavigateRiskRegister,
  pendingInputSeed,
  clearPendingInputSeed,
}: ChatPageProps) {
  const welcomeMessage = useMemo(() => buildWelcomeMessage(activeFunction), [activeFunction]);
  const [localMessages, setLocalMessages] = useState<ChatMessage[]>([
    welcomeMessage,
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const [emailTargetContent, setEmailTargetContent] = useState<string | null>(null);
  const [followupSeed, setFollowupSeed] = useState<string | null>(null);
  const [inputIsEmpty, setInputIsEmpty] = useState(true);
  const lockedFunctionRef = useRef<FunctionType | null>(null);
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

      const locked = lockedFunctionRef.current;
      lockedFunctionRef.current = null;

      sendMessageMutation.mutate(
        {
          message,
          conversation_id: conversationId,
          function_type: locked ?? activeFunction,
          routing_locked: locked !== null,
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

  const handleFollowupClick = useCallback(
    (followup: Followup) => {
      if (followup.kind === "navigate") {
        if (followup.target === "risk-register") {
          onNavigateRiskRegister();
        }
        return;
      }
      lockedFunctionRef.current = followup.mode;
      setFollowupSeed(followup.prefill);
    },
    [onNavigateRiskRegister],
  );

  const handleSeedConsumed = useCallback(() => {
    setFollowupSeed(null);
    clearPendingInputSeed();
  }, [clearPendingInputSeed]);

  const handleCopied = useCallback(() => {
    addToast("Copied to clipboard", "success");
  }, [addToast]);

  const handleCopyFailed = useCallback(() => {
    addToast("Copy failed — select the text manually", "error");
  }, [addToast]);

  const { latestAssistantId, latestFollowups } = useMemo<{
    latestAssistantId: string | null;
    latestFollowups: Followup[];
  }>(() => {
    for (let i = localMessages.length - 1; i >= 0; i--) {
      const m = localMessages[i];
      if (!m || m.role !== "assistant") continue;
      if (m.id.startsWith("welcome")) {
        return { latestAssistantId: null, latestFollowups: [] };
      }
      return {
        latestAssistantId: m.id,
        latestFollowups: extractFollowups(m.content).followups,
      };
    }
    return { latestAssistantId: null, latestFollowups: [] };
  }, [localMessages]);

  const [dismissedFollowupId, setDismissedFollowupId] = useState<string | null>(
    null,
  );

  const panelVisible =
    latestFollowups.length > 0 &&
    inputIsEmpty &&
    !isTyping &&
    dismissedFollowupId !== latestAssistantId;

  const handleDismissFollowups = useCallback(() => {
    setDismissedFollowupId(latestAssistantId);
  }, [latestAssistantId]);

  return (
    <>
      <MessageList
        messages={localMessages}
        isTyping={isTyping}
        {...(EMAIL_ON_CHAT_OUTPUT_ENABLED ? { onEmail: handleEmail } : {})}
        onCopied={handleCopied}
        onCopyFailed={handleCopyFailed}
      />
      <div className="relative">
        <FollowupPanel
          followups={latestFollowups}
          visible={panelVisible}
          onClick={handleFollowupClick}
          onDismiss={handleDismissFollowups}
        />
        <div className="relative z-10">
          <ChatInput
            onSend={handleSend}
            disabled={sendMessageMutation.isPending}
            seedValue={followupSeed ?? pendingInputSeed}
            onSeedConsumed={handleSeedConsumed}
            activeFunction={activeFunction}
            onInputChange={(value) => setInputIsEmpty(value.trim().length === 0)}
          />
        </div>
      </div>
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

interface FollowupPanelProps {
  followups: Followup[];
  visible: boolean;
  onClick: (followup: Followup) => void;
  onDismiss: () => void;
}

function FollowupPanel({
  followups,
  visible,
  onClick,
  onDismiss,
}: FollowupPanelProps) {
  return (
    <div
      className="pointer-events-none absolute inset-x-0 bottom-full overflow-hidden"
      aria-hidden={!visible}
    >
      <div
        className={clsx(
          "transition-transform duration-300 ease-out",
          visible
            ? "translate-y-0 pointer-events-auto"
            : "translate-y-full",
        )}
      >
        <div className="mx-auto max-w-3xl px-6 pb-3">
          <div className="relative rounded-2xl border border-gray-200 bg-white p-4 shadow-lg shadow-gray-900/10">
            <button
              type="button"
              onClick={onDismiss}
              tabIndex={visible ? 0 : -1}
              aria-label="Dismiss suggestions"
              className="absolute right-2 top-2 inline-flex h-6 w-6 items-center justify-center rounded-md text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
            >
              <X size={14} />
            </button>
            <p className="mb-3 pr-6 text-xs font-medium uppercase tracking-wider text-gray-500">
              What would you like to do next?
            </p>
            <div className="grid grid-cols-2 gap-2">
              {followups.map((f, i) => (
                <button
                  key={`${f.kind === "navigate" ? f.target : f.mode}-${i}`}
                  type="button"
                  onClick={() => onClick(f)}
                  className="group inline-flex items-center justify-between gap-1.5 rounded-xl border border-brand-200 bg-brand-50 px-3 py-2.5 text-xs font-medium text-brand-700 transition-colors hover:border-brand-300 hover:bg-brand-100"
                  tabIndex={visible ? 0 : -1}
                >
                  <span className="truncate text-left">{f.label}</span>
                  <ArrowRight
                    size={12}
                    className="shrink-0 opacity-60 transition-opacity group-hover:opacity-100"
                  />
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
