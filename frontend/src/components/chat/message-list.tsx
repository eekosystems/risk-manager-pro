import { clsx } from "clsx";
import { format } from "date-fns";
import { ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import type { ChatMessage, Citation } from "@/types/api";

import { CitationChip } from "./citation-chip";
import { CitationModal } from "./citation-modal";
import { MarkdownContent } from "./markdown-content";

interface MessageListProps {
  messages: ChatMessage[];
  isTyping: boolean;
  onSaveAsRisk?: (messageContent: string) => void;
}

interface SelectedCitation {
  citation: Citation;
  index: number;
}

export function MessageList({ messages, isTyping, onSaveAsRisk }: MessageListProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<SelectedCitation | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const handleClose = useCallback(() => setSelected(null), []);

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
              {msg.role === "assistant" && msg.id !== "welcome" && onSaveAsRisk && (
                <button
                  onClick={() => onSaveAsRisk(msg.content)}
                  className="mt-1 ml-1 flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] text-gray-400 transition-colors hover:bg-brand-50 hover:text-brand-500"
                  title="Save as Risk Entry"
                >
                  <ShieldAlert size={12} />
                  Save as Risk
                </button>
              )}
              <MessageTimestamp
                createdAt={msg.created_at}
                isUser={msg.role === "user"}
              />
            </div>
          </div>
        ))}

        {isTyping && (
          <div className="flex justify-start">
            <div className="flex items-center gap-1.5 rounded-2xl border border-gray-200 bg-white px-5 py-3.5 shadow-sm">
              {[0, 1, 2].map((i) => (
                <div
                  key={`dot-${i}`}
                  className="h-2 w-2 rounded-full bg-brand-400 animate-typing-dot"
                  style={{ animationDelay: `${i * 0.2}s` }}
                />
              ))}
            </div>
          </div>
        )}

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
