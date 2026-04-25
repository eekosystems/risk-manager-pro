import { useEffect, useRef, useState } from "react";
import { FileText, Loader2, MessageSquare, Search, X } from "lucide-react";

import { useSearch } from "@/hooks/use-search";
import type { ConversationHit, DocumentHit } from "@/types/api";

import type { AppView } from "../layout/app-layout";

interface SearchModalProps {
  open: boolean;
  onClose: () => void;
  onSelectConversation: (conversationId: string) => void;
  onViewChange: (view: AppView) => void;
}

export function SearchModal({
  open,
  onClose,
  onSelectConversation,
  onViewChange,
}: SearchModalProps) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { data, isLoading, isError } = useSearch(query);

  useEffect(() => {
    if (open) {
      setQuery("");
      // Focus on next tick after modal mounts
      const handle = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(handle);
    }
    return undefined;
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const handleConversation = (hit: ConversationHit) => {
    onSelectConversation(hit.id);
    onClose();
  };

  const handleDocument = (_hit: DocumentHit) => {
    // Documents are managed in Settings → Indexed Files; route there.
    onViewChange("chat");
    onClose();
  };

  const trimmed = query.trim();
  const showResults = trimmed.length >= 2;
  const conversations = data?.conversations ?? [];
  const documents = data?.documents ?? [];
  const totalResults = conversations.length + documents.length;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 px-4 pt-[10vh]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-xl border border-gray-200 bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 border-b border-gray-200 px-4 py-3">
          <Search size={18} className="text-gray-400" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search conversations and documents..."
            className="flex-1 bg-transparent text-sm text-slate-900 placeholder:text-gray-400 focus:outline-none"
          />
          {isLoading && showResults && (
            <Loader2 size={16} className="animate-spin text-brand-500" />
          )}
          <button
            onClick={onClose}
            className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            aria-label="Close search"
          >
            <X size={16} />
          </button>
        </div>

        <div className="max-h-[60vh] overflow-y-auto">
          {!showResults && (
            <p className="px-4 py-6 text-center text-sm text-gray-400">
              Type at least 2 characters to search.
            </p>
          )}

          {showResults && isError && (
            <p className="px-4 py-6 text-center text-sm text-red-500">
              Search failed. Try again.
            </p>
          )}

          {showResults && !isError && !isLoading && totalResults === 0 && (
            <p className="px-4 py-6 text-center text-sm text-gray-400">
              No matches.
            </p>
          )}

          {conversations.length > 0 && (
            <div>
              <p className="border-t border-gray-100 bg-gray-50 px-4 py-1.5 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                Conversations
              </p>
              {conversations.map((hit) => (
                <button
                  key={hit.id}
                  onClick={() => handleConversation(hit)}
                  className="flex w-full items-start gap-3 px-4 py-2.5 text-left hover:bg-brand-50"
                >
                  <MessageSquare
                    size={16}
                    className="mt-0.5 flex-shrink-0 text-brand-500"
                  />
                  <div className="flex flex-1 flex-col overflow-hidden">
                    <span className="truncate text-sm font-medium text-slate-900">
                      {hit.title}
                    </span>
                    <span className="truncate text-xs text-gray-500">{hit.snippet}</span>
                  </div>
                </button>
              ))}
            </div>
          )}

          {documents.length > 0 && (
            <div>
              <p className="border-t border-gray-100 bg-gray-50 px-4 py-1.5 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                Documents
              </p>
              {documents.map((hit) => (
                <button
                  key={hit.id}
                  onClick={() => handleDocument(hit)}
                  className="flex w-full items-start gap-3 px-4 py-2.5 text-left hover:bg-brand-50"
                >
                  <FileText
                    size={16}
                    className="mt-0.5 flex-shrink-0 text-brand-500"
                  />
                  <div className="flex flex-1 flex-col overflow-hidden">
                    <span className="truncate text-sm font-medium text-slate-900">
                      {hit.filename}
                    </span>
                    <span className="text-xs text-gray-500">
                      {hit.source_type.toUpperCase()} · {hit.status}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
