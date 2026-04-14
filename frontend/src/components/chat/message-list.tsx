import { clsx } from "clsx";
import { format } from "date-fns";
import { Check, Copy, Download, Mail, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { exportTextToPdf } from "@/lib/export-pdf";
import type { ChatMessage, Citation } from "@/types/api";

import { CitationChip } from "./citation-chip";
import { CitationModal } from "./citation-modal";
import { MarkdownContent } from "./markdown-content";

interface MessageListProps {
  messages: ChatMessage[];
  isTyping: boolean;
  onSaveAsRisk?: (messageContent: string) => void;
  onEmail?: (messageContent: string) => void;
  onCopied?: () => void;
  onCopyFailed?: () => void;
}

interface SelectedCitation {
  citation: Citation;
  index: number;
}

export function MessageList({
  messages,
  isTyping,
  onSaveAsRisk,
  onEmail,
  onCopied,
  onCopyFailed,
}: MessageListProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<SelectedCitation | null>(null);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const handleClose = useCallback(() => setSelected(null), []);

  const handleCopy = useCallback(
    async (messageId: string, content: string) => {
      try {
        await navigator.clipboard.writeText(content);
        setCopiedMessageId(messageId);
        onCopied?.();
        window.setTimeout(() => setCopiedMessageId(null), 2000);
      } catch {
        onCopyFailed?.();
      }
    },
    [onCopied, onCopyFailed],
  );

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6">
      <div className="mx-auto max-w-3xl space-y-6">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={clsx(
              "animate-slide-in",
              msg.role === "user" ? "flex justify-end" : "flex justify-start",
            )}
          >
            <div className="flex max-w-[85%] flex-col">
              {msg.role === "assistant" && (
                <div className="mb-1 ml-1">
                  <div className="h-2 w-2 rounded-full bg-green-500" />
                </div>
              )}
              <div
                className={clsx(
                  "rounded-2xl px-5 py-3.5",
                  msg.role === "user"
                    ? "gradient-brand text-white shadow-md shadow-brand-500/20"
                    : "border border-gray-200 bg-white text-gray-800 shadow-sm",
                )}
              >
                {msg.role === "assistant" ? (
                  <MarkdownContent
                    content={msg.content}
                    citations={msg.citations ?? undefined}
                    onCitationClick={(idx) => {
                      const c = msg.citations?.[idx];
                      if (c) setSelected({ citation: c, index: idx });
                    }}
                  />
                ) : (
                  <div className="whitespace-pre-wrap text-sm leading-relaxed">
                    {msg.content}
                  </div>
                )}

                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5 border-t border-gray-100 pt-3">
                    {msg.citations.map((c, i) => (
                      <CitationChip
                        key={c.chunk_id ?? `citation-${i}`}
                        citation={c}
                        index={i}
                        onClick={() => setSelected({ citation: c, index: i })}
                      />
                    ))}
                  </div>
                )}
              </div>
              {msg.role === "assistant" && !msg.id.startsWith("welcome") && (
                <div className="mt-1 ml-1 flex flex-wrap items-center gap-1">
                  {onSaveAsRisk && (
                    <ActionButton
                      icon={<ShieldAlert size={12} />}
                      label="Add to Risk Registry"
                      onClick={() => onSaveAsRisk(msg.content)}
                    />
                  )}
                  <ActionButton
                    icon={
                      copiedMessageId === msg.id ? (
                        <Check size={12} />
                      ) : (
                        <Copy size={12} />
                      )
                    }
                    label={copiedMessageId === msg.id ? "Copied" : "Copy"}
                    onClick={() => handleCopy(msg.id, msg.content)}
                  />
                  {onEmail && (
                    <ActionButton
                      icon={<Mail size={12} />}
                      label="Send Email"
                      onClick={() => onEmail(msg.content)}
                    />
                  )}
                  <ActionButton
                    icon={<Download size={12} />}
                    label="Export PDF"
                    onClick={() => exportTextToPdf(msg.content)}
                  />
                </div>
              )}
              <MessageTimestamp
                createdAt={msg.created_at}
                isUser={msg.role === "user"}
              />
            </div>
          </div>
        ))}

        {isTyping && <TypingIndicator />}

        <div ref={endRef} />
      </div>

      {selected && (
        <CitationModal
          citation={selected.citation}
          index={selected.index}
          onClose={handleClose}
        />
      )}
    </div>
  );
}

interface ActionButtonProps {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}

function ActionButton({ icon, label, onClick }: ActionButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] text-gray-400 transition-colors hover:bg-brand-50 hover:text-brand-500"
      title={label}
    >
      {icon}
      {label}
    </button>
  );
}

const THINKING_PHRASES = [
  "Searching safety documents…",
  "Reviewing relevant sources…",
  "Cross-referencing regulations…",
  "Analyzing risk factors…",
  "Drafting response…",
];

function TypingIndicator() {
  const [phraseIdx, setPhraseIdx] = useState(0);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setPhraseIdx((i) => (i + 1) % THINKING_PHRASES.length);
    }, 2200);
    return () => window.clearInterval(interval);
  }, []);

  return (
    <div className="flex justify-start">
      <div className="flex flex-col items-start">
        <div className="flex items-center gap-1.5 rounded-2xl border border-gray-200 bg-white px-5 py-3.5 shadow-sm">
          {[0, 1, 2].map((i) => (
            <div
              key={`dot-${i}`}
              className="h-2 w-2 rounded-full bg-brand-400 animate-typing-dot"
              style={{ animationDelay: `${i * 0.2}s` }}
            />
          ))}
        </div>
        <span
          key={phraseIdx}
          className="animate-thinking-phrase mt-1 px-1 text-[11px] italic text-gray-400"
        >
          {THINKING_PHRASES[phraseIdx]}
        </span>
      </div>
    </div>
  );
}

interface MessageTimestampProps {
  createdAt: string;
  isUser: boolean;
}

function MessageTimestamp({ createdAt, isUser }: MessageTimestampProps) {
  return (
    <div
      className={clsx(
        "mt-1 px-1",
        isUser ? "text-right" : "text-left",
      )}
    >
      <span className="text-[11px] text-gray-400">
        {format(new Date(createdAt), "hh:mm a").toUpperCase()}
      </span>
    </div>
  );
}
