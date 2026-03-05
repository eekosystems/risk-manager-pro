import { clsx } from "clsx";
import { format } from "date-fns";
import { useEffect, useRef } from "react";

import type { ChatMessage } from "@/types/api";

import { CitationChip } from "./citation-chip";
import { MarkdownContent } from "./markdown-content";

interface MessageListProps {
  messages: ChatMessage[];
  isTyping: boolean;
}

export function MessageList({ messages, isTyping }: MessageListProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

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
              <div
                className={clsx(
                  "rounded-2xl px-5 py-3.5",
                  msg.role === "user"
                    ? "gradient-brand text-white shadow-md shadow-brand-500/20"
                    : "border border-gray-200 bg-white text-gray-800 shadow-sm",
                )}
              >
                {msg.role === "assistant" ? (
                  <MarkdownContent content={msg.content} />
                ) : (
                  <div className="whitespace-pre-wrap text-sm leading-relaxed">
                    {msg.content}
                  </div>
                )}

                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5 border-t border-gray-100 pt-3">
                    {msg.citations.map((c, i) => (
                      <CitationChip key={c.chunk_id ?? i} citation={c} index={i} />
                    ))}
                  </div>
                )}
              </div>
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
                  key={i}
                  className="h-2 w-2 rounded-full bg-brand-400"
                  style={{
                    animation: `typingDot 1.2s infinite`,
                    animationDelay: `${i * 0.2}s`,
                  }}
                />
              ))}
            </div>
          </div>
        )}

        <div ref={endRef} />
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
        "mt-1 flex items-center gap-1 px-1",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      {!isUser && (
        <div className="h-1.5 w-1.5 rounded-full bg-green-500" />
      )}
      <span className="text-[11px] text-gray-400">
        {format(new Date(createdAt), "h:mm a")}
      </span>
    </div>
  );
}
