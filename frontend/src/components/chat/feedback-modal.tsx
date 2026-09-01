import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Loader2, ThumbsDown, ThumbsUp, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { submitFeedback } from "@/api/feedback";
import type { FeedbackRating } from "@/types/api";

interface FeedbackModalProps {
  conversationId: string;
  messageId: string;
  onClose: () => void;
}

const MAX_COMMENT = 5000;

export function FeedbackModal({
  conversationId,
  messageId,
  onClose,
}: FeedbackModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const [rating, setRating] = useState<FeedbackRating | null>(null);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const mutation = useMutation({
    mutationFn: submitFeedback,
    onSuccess: () => {
      setSubmitted(true);
      // Leave the confirmation up briefly so it registers, then close.
      setTimeout(onClose, 1600);
    },
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

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!rating || !comment.trim()) return;
    mutation.mutate({
      conversationId,
      messageId,
      rating,
      comment: comment.trim(),
    });
  }

  const canSubmit = Boolean(rating) && comment.trim().length > 0;

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Give feedback on this response"
    >
      <div className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-100 bg-gray-50 px-6 py-4">
          <h3 className="text-sm font-semibold text-gray-900">
            Feedback on this response
          </h3>
          <button
            onClick={onClose}
            aria-label="Close feedback"
            className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-200 hover:text-gray-600"
          >
            <X size={18} />
          </button>
        </div>

        {submitted ? (
          <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
            <CheckCircle2 size={32} className="text-brand-500" />
            <p className="text-sm font-medium text-slate-800">Thank you</p>
            <p className="max-w-xs text-[12px] text-slate-500">
              Your feedback goes to the review queue. Approved feedback becomes
              permanent guidance that shapes future answers.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="px-6 py-5">
            <fieldset className="mb-4">
              <legend className="mb-2 text-[12px] font-semibold text-slate-700">
                Was this response useful?
              </legend>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setRating("helpful")}
                  aria-pressed={rating === "helpful"}
                  className={`flex flex-1 items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-semibold transition-colors ${
                    rating === "helpful"
                      ? "border-brand-500 bg-brand-50 text-brand-700"
                      : "border-gray-200 text-slate-500 hover:bg-gray-50"
                  }`}
                >
                  <ThumbsUp size={15} />
                  Useful
                </button>
                <button
                  type="button"
                  onClick={() => setRating("not_helpful")}
                  aria-pressed={rating === "not_helpful"}
                  className={`flex flex-1 items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-semibold transition-colors ${
                    rating === "not_helpful"
                      ? "border-amber-400 bg-amber-50 text-amber-700"
                      : "border-gray-200 text-slate-500 hover:bg-gray-50"
                  }`}
                >
                  <ThumbsDown size={15} />
                  Needs work
                </button>
              </div>
            </fieldset>

            <label
              htmlFor="feedback-comment"
              className="mb-1.5 block text-[12px] font-semibold text-slate-700"
            >
              What should it have done differently?
            </label>
            <textarea
              id="feedback-comment"
              autoFocus
              rows={5}
              value={comment}
              maxLength={MAX_COMMENT}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Be specific — the clearer the correction, the more likely it becomes a permanent rule. For example: cite AC 150/5340-30 alongside 14 CFR 139.337 on runway incursion findings."
              className="w-full resize-y rounded-xl border border-gray-200 px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
            <div className="mt-1 flex items-center justify-between">
              <p className="text-[11px] text-slate-400">
                Reviewed by an administrator before it changes anything.
              </p>
              <span className="text-[11px] text-slate-400">
                {comment.length}/{MAX_COMMENT}
              </span>
            </div>

            {mutation.isError && (
              <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
                Your feedback could not be sent. Please try again.
              </div>
            )}

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-semibold text-slate-600 transition-colors hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!canSubmit || mutation.isPending}
                className="flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:opacity-40"
              >
                {mutation.isPending && (
                  <Loader2 size={14} className="animate-spin" />
                )}
                Send feedback
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
