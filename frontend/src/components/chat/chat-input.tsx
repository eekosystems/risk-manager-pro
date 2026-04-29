import { Paperclip, Send, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";

import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { FUNCTIONS } from "@/constants/functions";
import { useFileUpload } from "@/hooks/use-file-upload";
import type { FunctionType } from "@/types/api";

interface ChatInputProps {
  onSend: (message: string, files: File[]) => void;
  disabled: boolean;
  seedValue?: string | null;
  onSeedConsumed?: () => void;
  activeFunction?: FunctionType;
}

export function ChatInput({
  onSend,
  disabled,
  seedValue,
  onSeedConsumed,
  activeFunction,
}: ChatInputProps) {
  const modeLabel = activeFunction
    ? FUNCTIONS.find((f) => f.id === activeFunction)?.shortName ??
      FUNCTIONS.find((f) => f.id === activeFunction)?.name ??
      null
    : null;
  const [input, setInput] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { files, addFiles, removeFile, clearFiles } = useFileUpload();

  useEffect(() => {
    if (seedValue) {
      setInput(seedValue);
      onSeedConsumed?.();
      requestAnimationFrame(() => {
        const el = textareaRef.current;
        if (!el) return;
        el.focus();
        el.setSelectionRange(el.value.length, el.value.length);
        el.scrollTop = el.scrollHeight;
      });
    }
  }, [seedValue, onSeedConsumed]);

  const handleSend = useCallback(() => {
    if (!input.trim() && files.length === 0) return;
    onSend(
      input.trim(),
      files.map((f) => f.file),
    );
    setInput("");
    clearFiles();
  }, [input, files, onSend, clearFiles]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-gray-200 bg-white px-6 py-4">
      <div className="mx-auto max-w-3xl">
        {modeLabel && (
          <div className="mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-gray-500">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-brand-400" />
            Mode: {modeLabel}
          </div>
        )}
        {files.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-2">
            {files.map((f) => (
              <div
                key={f.id}
                className="flex items-center gap-2 rounded-lg bg-gray-100 px-3 py-1.5 text-sm"
              >
                <span className="max-w-[120px] truncate text-gray-700">
                  {f.name}
                </span>
                <span className="text-[11px] text-gray-400">{f.size}</span>
                <button
                  onClick={() => removeFile(f.id)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div
          className={`flex items-end gap-3 rounded-2xl border bg-white px-4 py-3 shadow-sm transition-all ${
            isDragging
              ? "border-brand-400 bg-brand-50"
              : "border-gray-200 focus-within:border-brand-300 focus-within:shadow-md focus-within:shadow-brand-500/5"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            if (e.dataTransfer.files.length > 0) {
              addFiles(e.dataTransfer.files);
            }
          }}
        >
          <button
            onClick={() => fileInputRef.current?.click()}
            className="mb-0.5 rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <Paperclip size={18} />
          </button>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.txt"
            className="hidden"
            onChange={(e) => e.target.files && addFiles(e.target.files)}
          />

          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe system changes, ask about regulations, or request analysis..."
            className="max-h-32 min-h-[24px] flex-1 resize-none bg-transparent text-sm text-gray-800 placeholder:text-gray-400 focus:outline-none"
            rows={1}
            disabled={disabled}
          />

          <button
            onClick={handleSend}
            disabled={disabled || (!input.trim() && files.length === 0)}
            className="mb-0.5 flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-r from-brand-500 to-brand-400 text-white shadow-md shadow-brand-500/25 transition-all hover:scale-105 hover:shadow-lg disabled:opacity-50 disabled:shadow-none"
          >
            {disabled ? (
              <LoadingSpinner size="sm" className="border-white/30 border-t-white" />
            ) : (
              <Send size={16} />
            )}
          </button>
        </div>

        <p className="mt-2 text-center text-[11px] text-gray-400">
          Press{" "}
          <kbd className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[11px] font-medium text-gray-500">
            Enter
          </kbd>{" "}
          to send
          <span className="mx-1.5 text-gray-300">&#183;</span>
          Attach files
          <span className="mx-1.5 text-gray-300">&#183;</span>
          AI-powered analysis
        </p>
      </div>
    </div>
  );
}
