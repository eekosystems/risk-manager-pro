import { useState } from "react";
import { Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";

interface EmailChatModalProps {
  content: string;
  onClose: () => void;
  onSubmit: (payload: { to: string; subject: string; content: string }) => void;
  isPending: boolean;
}

export function EmailChatModal({
  content,
  onClose,
  onSubmit,
  isPending,
}: EmailChatModalProps) {
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("Risk Manager Pro — AI response");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!to.trim() || !subject.trim()) return;
    onSubmit({ to: to.trim(), subject: subject.trim(), content });
  }

  const inputClass =
    "w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20";
  const labelClass = "block text-sm font-semibold text-slate-700 mb-1";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-xl rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
          <h2 className="text-lg font-bold text-slate-900">Send AI response by email</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5">
          <div className="space-y-4">
            <div>
              <label className={labelClass}>Send to</label>
              <input
                type="email"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                placeholder="recipient@example.com"
                className={inputClass}
                required
                autoFocus
              />
            </div>

            <div>
              <label className={labelClass}>Subject</label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className={inputClass}
                required
                maxLength={200}
              />
            </div>

            <div>
              <label className={labelClass}>Preview</label>
              <div className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-xs text-slate-700">
                {content}
              </div>
            </div>
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose} disabled={isPending}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={isPending || !to.trim()}>
              {isPending ? (
                <>
                  <Loader2 size={16} className="mr-1.5 animate-spin" />
                  Sending...
                </>
              ) : (
                "Send"
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
