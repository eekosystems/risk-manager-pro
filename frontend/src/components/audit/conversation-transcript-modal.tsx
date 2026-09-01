import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { AlertTriangle, Loader2, MessageSquare, User, X } from "lucide-react";
import { useEffect, useRef } from "react";

import { getConversationTranscript } from "@/api/chat";
import { MarkdownContent } from "@/components/chat/markdown-content";

interface ConversationTranscriptModalProps {
  conversationId: string;
  onClose: () => void;
}

/**
 * Read-only view of another user's conversation, opened from an audit log row.
 *
 * Deliberately offers no way to reply, delete, or email — this is a
 * supervisory read, and the server records every open in the audit log.
 */
export function ConversationTranscriptModal({
  conversationId,
  onClose,
}: ConversationTranscriptModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["conversation-transcript", conversationId],
    queryFn: () => getConversationTranscript(conversationId),
    retry: false,
  });

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  function handleOverlayClick(e: React.MouseEvent) {
    if (e.target === overlayRef.current) onClose();
  }

  const status = (error as { response?: { status?: number } })?.response?.status;
  const errorMessage =
    status === 403
      ? "You need the organization administrator role to read another user's conversation."
      : status === 404
        ? "That conversation no longer exists, or it belongs to a different organization."
        : "The conversation could not be loaded.";

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Conversation transcript"
    >
      <div className="relative flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-gray-100 bg-gray-50 px-6 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <MessageSquare size={16} className="shrink-0 text-brand-500" />
              <h3 className="truncate text-sm font-semibold text-gray-900">
                {data?.title ?? "Conversation transcript"}
              </h3>
            </div>
            {data && (
              <div className="mt-1 flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
                <span className="flex items-center gap-1">
                  <User size={11} />
                  {data.author.display_name}
                </span>
                <span>{format(new Date(data.created_at), "MMM d, yyyy HH:mm")}</span>
                <span>
                  {data.messages.length}{" "}
                  {data.messages.length === 1 ? "message" : "messages"}
                </span>
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close transcript"
            className="shrink-0 rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-200 hover:text-gray-600"
          >
            <X size={18} />
          </button>
        </div>

        {/* Access notice — this read is itself an audited event. */}
        <div className="flex items-start gap-2 border-b border-amber-100 bg-amber-50 px-6 py-2.5">
          <AlertTriangle size={13} className="mt-0.5 shrink-0 text-amber-500" />
          <p className="text-[11px] leading-snug text-amber-800">
            You are viewing another user&apos;s conversation as an organization
            administrator. This access has been recorded in the audit log.
          </p>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {isLoading && (
            <div className="flex items-center justify-center py-16">
              <Loader2 size={22} className="animate-spin text-brand-500" />
            </div>
          )}

          {isError && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {errorMessage}
            </div>
          )}

          {data && data.messages.length === 0 && (
            <p className="py-12 text-center text-sm text-slate-400">
              This conversation has no messages.
            </p>
          )}

          {data && data.messages.length > 0 && (
            <div className="space-y-4">
              {data.messages.map((message) => (
                <div key={message.id}>
                  <div className="mb-1 flex items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                        message.role === "user"
                          ? "bg-brand-50 text-brand-700"
                          : "bg-gray-100 text-slate-600"
                      }`}
                    >
                      {message.role === "user" ? data.author.display_name : "Assistant"}
                    </span>
                    <span className="text-[10px] text-slate-400">
                      {format(new Date(message.created_at), "MMM d, HH:mm:ss")}
                    </span>
                  </div>
                  <div
                    className={`rounded-xl border px-4 py-3 ${
                      message.role === "user"
                        ? "border-brand-100 bg-brand-50/40"
                        : "border-gray-200 bg-white"
                    }`}
                  >
                    {message.role === "assistant" ? (
                      <MarkdownContent content={message.content} />
                    ) : (
                      <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
                        {message.content}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
