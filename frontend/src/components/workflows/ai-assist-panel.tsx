import { Loader2, MessageSquare, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { useSendMessage } from "@/hooks/use-chat";
import type { ChatMessage, FunctionType } from "@/types/api";

import { MarkdownContent } from "../chat/markdown-content";

interface AiAssistPanelProps {
  isOpen: boolean;
  onClose: () => void;
  functionType: FunctionType;
  contextMessage: string;
  conversationId: string | null;
  onConversationId: (id: string) => void;
}

export function AiAssistPanel({
  isOpen,
  onClose,
  functionType,
  contextMessage,
  conversationId,
  onConversationId,
}: AiAssistPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [hasInitialized, setHasInitialized] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const sendMutation = useSendMessage();

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const sendContextMessage = useCallback(
    (content: string) => {
      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content,
        citations: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsTyping(true);

      sendMutation.mutate(
        {
          message: content,
          conversation_id: conversationId,
          function_type: functionType,
        },
        {
          onSuccess: (data) => {
            setIsTyping(false);
            onConversationId(data.conversation_id);
            setMessages((prev) => [...prev, data.message]);
          },
          onError: () => {
            setIsTyping(false);
            setMessages((prev) => [
              ...prev,
              {
                id: `error-${Date.now()}`,
                role: "assistant",
                content: "Sorry, I encountered an error. Please try again.",
                citations: null,
                created_at: new Date().toISOString(),
              },
            ]);
          },
        },
      );
    },
    [conversationId, functionType, onConversationId, sendMutation],
  );

  useEffect(() => {
    if (isOpen && !hasInitialized && contextMessage) {
      setHasInitialized(true);
      sendContextMessage(contextMessage);
    }
  }, [isOpen, hasInitialized, contextMessage, sendContextMessage]);

  const handleSend = useCallback(() => {
    if (!input.trim() || sendMutation.isPending) return;
    const msg = input.trim();
    setInput("");
    sendContextMessage(msg);
  }, [input, sendMutation.isPending, sendContextMessage]);

  if (!isOpen) return null;

  return (
    <div className="flex h-full w-[400px] min-w-[400px] flex-col border-l border-gray-200 bg-white">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <div className="flex items-center gap-2">
          <MessageSquare size={16} className="text-brand-500" />
          <span className="text-sm font-bold text-slate-800">AI Assistant</span>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
        >
          <X size={16} />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <div className="space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={msg.role === "user" ? "flex justify-end" : "flex justify-start"}
            >
              <div
                className={
                  msg.role === "user"
                    ? "max-w-[85%] rounded-2xl gradient-brand px-4 py-2.5 text-sm text-white shadow-sm"
                    : "max-w-[85%] rounded-2xl border border-gray-200 bg-white px-4 py-2.5 text-sm text-gray-800 shadow-sm"
                }
              >
                {msg.role === "assistant" ? (
                  <MarkdownContent content={msg.content} />
                ) : (
                  <span className="whitespace-pre-wrap text-sm leading-relaxed">
                    {msg.content}
                  </span>
                )}
              </div>
            </div>
          ))}
          {isTyping && (
            <div className="flex justify-start">
              <div className="flex items-center gap-1.5 rounded-2xl border border-gray-200 bg-white px-4 py-2.5 shadow-sm">
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
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 px-4 py-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask AI for help..."
            className="flex-1 rounded-xl border border-gray-200 px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
          <Button
            size="sm"
            onClick={handleSend}
            disabled={!input.trim() || sendMutation.isPending}
          >
            {sendMutation.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              "Send"
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
