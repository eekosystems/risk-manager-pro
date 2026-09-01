import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import {
  Brain,
  Check,
  Loader2,
  MessageSquare,
  Power,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  X,
} from "lucide-react";
import { useState } from "react";

import {
  createGuidance,
  deleteGuidance,
  getFeedback,
  getGuidance,
  promoteFeedback,
  reviewFeedback,
  updateGuidance,
} from "@/api/feedback";
import type {
  ApplicationGuidance,
  FeedbackReviewItem,
  FeedbackStatus,
  FunctionType,
  GuidanceScope,
} from "@/types/api";

const STATUS_STYLES: Record<FeedbackStatus, string> = {
  new: "bg-brand-50 text-brand-700",
  reviewed: "bg-gray-100 text-slate-600",
  promoted: "bg-green-50 text-green-700",
  dismissed: "bg-gray-100 text-slate-400",
};

const FUNCTION_LABELS: Record<FunctionType, string> = {
  phl: "PHL",
  sra: "SRA",
  system: "System Analysis",
  general: "General",
  risk_register: "Risk Register",
};

const FUNCTION_OPTIONS: FunctionType[] = [
  "general",
  "phl",
  "sra",
  "system",
  "risk_register",
];

type Section = "queue" | "guidance";

export function FeedbackTab() {
  const [section, setSection] = useState<Section>("queue");

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-slate-900">Feedback &amp; Training</h2>
        <p className="text-sm text-slate-500">
          Review what users say about the AI&apos;s answers, and promote the useful
          corrections into permanent guidance that shapes every future response.
        </p>
      </div>

      <div className="mb-5 flex gap-2 border-b border-gray-200">
        <SectionTab
          active={section === "queue"}
          onClick={() => setSection("queue")}
          icon={<MessageSquare size={14} />}
          label="Review Queue"
        />
        <SectionTab
          active={section === "guidance"}
          onClick={() => setSection("guidance")}
          icon={<Brain size={14} />}
          label="Application Guidance"
        />
      </div>

      {section === "queue" ? <ReviewQueue /> : <GuidanceStore />}
    </div>
  );
}

function SectionTab({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-semibold transition-colors ${
        active
          ? "border-brand-500 text-brand-700"
          : "border-transparent text-slate-400 hover:text-slate-600"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

// --- Review queue ---

function ReviewQueue() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<FeedbackStatus | "">("new");
  const [promoting, setPromoting] = useState<FeedbackReviewItem | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["feedback", statusFilter],
    queryFn: () =>
      getFeedback(statusFilter ? { status: statusFilter } : {}),
    retry: false,
  });

  const reviewMutation = useMutation({
    mutationFn: reviewFeedback,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["feedback"] });
    },
  });

  const items = data?.data ?? [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 size={22} className="animate-spin text-brand-500" />
      </div>
    );
  }

  return (
    <>
      <div className="mb-4 flex items-center gap-2">
        <label htmlFor="feedback-status" className="text-[12px] text-slate-500">
          Status
        </label>
        <select
          id="feedback-status"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as FeedbackStatus | "")}
          className="rounded-lg border border-gray-200 px-3 py-1.5 text-[12px] text-slate-700 focus:border-brand-500 focus:outline-none"
        >
          <option value="">All</option>
          <option value="new">New</option>
          <option value="reviewed">Reviewed</option>
          <option value="promoted">Promoted</option>
          <option value="dismissed">Dismissed</option>
        </select>
        <span className="ml-auto text-[12px] text-slate-400">
          {data?.total ?? 0} total
        </span>
      </div>

      {items.length === 0 ? (
        <div className="rounded-2xl border border-gray-200 bg-white p-10 text-center text-sm text-slate-400">
          No feedback in this state yet.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <article
              key={item.id}
              className="rounded-2xl border border-gray-200 bg-white p-5"
            >
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <span
                  className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                    item.rating === "helpful"
                      ? "bg-brand-50 text-brand-700"
                      : "bg-amber-50 text-amber-700"
                  }`}
                >
                  {item.rating === "helpful" ? (
                    <ThumbsUp size={10} />
                  ) : (
                    <ThumbsDown size={10} />
                  )}
                  {item.rating === "helpful" ? "Useful" : "Needs work"}
                </span>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${STATUS_STYLES[item.status]}`}
                >
                  {item.status}
                </span>
                <span className="text-[11px] text-slate-400">
                  {item.submitter_name}
                </span>
                <span className="text-[11px] text-slate-400">
                  {format(new Date(item.created_at), "MMM d, yyyy HH:mm")}
                </span>
              </div>

              <p className="mb-3 whitespace-pre-wrap text-sm text-slate-800">
                {item.comment}
              </p>

              <details className="mb-3 rounded-xl border border-gray-100 bg-gray-50 px-3 py-2">
                <summary className="cursor-pointer text-[11px] font-semibold text-slate-500">
                  The response this refers to
                </summary>
                <p className="mt-2 whitespace-pre-wrap text-[12px] leading-relaxed text-slate-600">
                  {item.message_excerpt || "(the message is no longer available)"}
                </p>
              </details>

              {item.status !== "promoted" && (
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => setPromoting(item)}
                    className="flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-1.5 text-[12px] font-semibold text-white transition-colors hover:bg-brand-700"
                  >
                    <Sparkles size={13} />
                    Add to application training
                  </button>
                  <button
                    onClick={() =>
                      reviewMutation.mutate({
                        feedbackId: item.id,
                        status: "reviewed",
                      })
                    }
                    disabled={reviewMutation.isPending}
                    className="flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-[12px] font-semibold text-slate-600 transition-colors hover:bg-gray-50 disabled:opacity-40"
                  >
                    <Check size={13} />
                    Mark reviewed
                  </button>
                  <button
                    onClick={() =>
                      reviewMutation.mutate({
                        feedbackId: item.id,
                        status: "dismissed",
                      })
                    }
                    disabled={reviewMutation.isPending}
                    className="flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-[12px] font-semibold text-slate-500 transition-colors hover:bg-gray-50 disabled:opacity-40"
                  >
                    <X size={13} />
                    Dismiss
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      )}

      {promoting && (
        <PromoteModal item={promoting} onClose={() => setPromoting(null)} />
      )}
    </>
  );
}

// --- Promote to guidance ---

function PromoteModal({
  item,
  onClose,
}: {
  item: FeedbackReviewItem;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  // Seed from the user's own words — the admin edits it into an instruction.
  const [content, setContent] = useState(item.comment);
  const [scope, setScope] = useState<GuidanceScope>("organization");
  const [functionType, setFunctionType] = useState<FunctionType | "">("");

  const mutation = useMutation({
    mutationFn: promoteFeedback,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["feedback"] });
      void queryClient.invalidateQueries({ queryKey: ["guidance"] });
      onClose();
    },
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Add to application training"
    >
      <div className="w-full max-w-xl overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-100 bg-gray-50 px-6 py-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
            <Sparkles size={15} className="text-brand-500" />
            Add to application training
          </h3>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-200 hover:text-gray-600"
          >
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-5">
          <p className="mb-4 rounded-xl border border-brand-100 bg-brand-50/50 px-3 py-2 text-[11px] leading-snug text-brand-800">
            Write this as a direct instruction to the model. It is added to the
            system prompt on every matching answer from now on, so keep it to one
            specific rule. You can deactivate it at any time.
          </p>

          <label
            htmlFor="guidance-content"
            className="mb-1.5 block text-[12px] font-semibold text-slate-700"
          >
            Guidance rule
          </label>
          <textarea
            id="guidance-content"
            rows={4}
            value={content}
            maxLength={2000}
            onChange={(e) => setContent(e.target.value)}
            placeholder="When assessing runway incursions, cite AC 150/5340-30 alongside 14 CFR 139.337."
            className="w-full resize-y rounded-xl border border-gray-200 px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />

          <div className="mt-4 grid grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="guidance-scope"
                className="mb-1.5 block text-[12px] font-semibold text-slate-700"
              >
                Applies to
              </label>
              <select
                id="guidance-scope"
                value={scope}
                onChange={(e) => setScope(e.target.value as GuidanceScope)}
                className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm text-slate-700 focus:border-brand-500 focus:outline-none"
              >
                <option value="organization">
                  This organization only
                </option>
                <option value="global">Every organization</option>
              </select>
            </div>
            <div>
              <label
                htmlFor="guidance-function"
                className="mb-1.5 block text-[12px] font-semibold text-slate-700"
              >
                Function
              </label>
              <select
                id="guidance-function"
                value={functionType}
                onChange={(e) =>
                  setFunctionType(e.target.value as FunctionType | "")
                }
                className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm text-slate-700 focus:border-brand-500 focus:outline-none"
              >
                <option value="">All functions</option>
                {FUNCTION_OPTIONS.map((f) => (
                  <option key={f} value={f}>
                    {FUNCTION_LABELS[f]}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {mutation.isError && (
            <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
              The rule could not be saved. Check the wording and try again.
            </div>
          )}

          <div className="mt-5 flex justify-end gap-2">
            <button
              onClick={onClose}
              className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={() =>
                mutation.mutate({
                  feedbackId: item.id,
                  content: content.trim(),
                  scope,
                  functionType: functionType || null,
                })
              }
              disabled={!content.trim() || mutation.isPending}
              className="flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-40"
            >
              {mutation.isPending && (
                <Loader2 size={14} className="animate-spin" />
              )}
              Activate rule
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Guidance store ---

function GuidanceStore() {
  const queryClient = useQueryClient();
  const [newRule, setNewRule] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const { data: rules = [], isLoading } = useQuery({
    queryKey: ["guidance"],
    queryFn: getGuidance,
    retry: false,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["guidance"] });
  };

  const createMutation = useMutation({
    mutationFn: createGuidance,
    onSuccess: () => {
      setNewRule("");
      invalidate();
    },
  });
  const updateMutation = useMutation({
    mutationFn: updateGuidance,
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({
    mutationFn: deleteGuidance,
    onSuccess: () => {
      setDeleteConfirm(null);
      invalidate();
    },
  });

  function handleDelete(id: string) {
    if (deleteConfirm === id) {
      deleteMutation.mutate(id);
    } else {
      setDeleteConfirm(id);
      setTimeout(() => setDeleteConfirm(null), 3000);
    }
  }

  const active = rules.filter((r) => r.is_active).length;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 size={22} className="animate-spin text-brand-500" />
      </div>
    );
  }

  return (
    <>
      <div className="mb-5 rounded-2xl border border-gray-200 bg-white p-5">
        <h3 className="mb-1 text-sm font-semibold text-slate-800">
          Add a rule directly
        </h3>
        <p className="mb-3 text-[12px] text-slate-500">
          Applies to every organization. For a rule scoped to one client, promote
          it from that client&apos;s feedback instead.
        </p>
        <textarea
          rows={3}
          value={newRule}
          maxLength={2000}
          onChange={(e) => setNewRule(e.target.value)}
          placeholder="Always state the residual risk cell label before the qualitative band."
          className="w-full resize-y rounded-xl border border-gray-200 px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
        />
        <div className="mt-2 flex justify-end">
          <button
            onClick={() =>
              createMutation.mutate({ content: newRule.trim(), scope: "global" })
            }
            disabled={!newRule.trim() || createMutation.isPending}
            className="flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2 text-[12px] font-semibold text-white hover:bg-brand-700 disabled:opacity-40"
          >
            {createMutation.isPending && (
              <Loader2 size={13} className="animate-spin" />
            )}
            Add rule
          </button>
        </div>
      </div>

      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-800">
          Active guidance
        </h3>
        <span className="text-[12px] text-slate-400">
          {active} active of {rules.length}
        </span>
      </div>

      {rules.length === 0 ? (
        <div className="rounded-2xl border border-gray-200 bg-white p-10 text-center text-sm text-slate-400">
          No guidance yet. Promote feedback from the review queue, or add a rule
          above.
        </div>
      ) : (
        <div className="space-y-2">
          {rules.map((rule) => (
            <GuidanceRow
              key={rule.id}
              rule={rule}
              onToggle={() =>
                updateMutation.mutate({
                  guidanceId: rule.id,
                  isActive: !rule.is_active,
                })
              }
              onDelete={() => handleDelete(rule.id)}
              isDeleteConfirm={deleteConfirm === rule.id}
              isBusy={updateMutation.isPending || deleteMutation.isPending}
            />
          ))}
        </div>
      )}
    </>
  );
}

function GuidanceRow({
  rule,
  onToggle,
  onDelete,
  isDeleteConfirm,
  isBusy,
}: {
  rule: ApplicationGuidance;
  onToggle: () => void;
  onDelete: () => void;
  isDeleteConfirm: boolean;
  isBusy: boolean;
}) {
  return (
    <div
      className={`flex items-start gap-3 rounded-2xl border bg-white p-4 ${
        rule.is_active ? "border-gray-200" : "border-gray-100 opacity-60"
      }`}
    >
      <div className="min-w-0 flex-1">
        <p className="mb-2 whitespace-pre-wrap text-sm text-slate-800">
          {rule.content}
        </p>
        <div className="flex flex-wrap items-center gap-2 text-[10px]">
          <span
            className={`rounded-full px-2 py-0.5 font-bold ${
              rule.scope === "global"
                ? "bg-accent-50 text-accent-700"
                : "bg-brand-50 text-brand-700"
            }`}
          >
            {rule.scope === "global" ? "All organizations" : "One organization"}
          </span>
          <span className="rounded-full bg-gray-100 px-2 py-0.5 font-bold text-slate-600">
            {rule.function_type
              ? FUNCTION_LABELS[rule.function_type]
              : "All functions"}
          </span>
          {rule.source_feedback_id && (
            <span className="text-slate-400">from user feedback</span>
          )}
          <span className="text-slate-400">
            {format(new Date(rule.created_at), "MMM d, yyyy")}
          </span>
        </div>
      </div>

      <button
        onClick={onToggle}
        disabled={isBusy}
        title={rule.is_active ? "Deactivate this rule" : "Reactivate this rule"}
        className={`shrink-0 rounded-lg p-1.5 transition-colors disabled:opacity-40 ${
          rule.is_active
            ? "text-brand-500 hover:bg-brand-50"
            : "text-gray-300 hover:bg-gray-50 hover:text-gray-500"
        }`}
      >
        <Power size={14} />
      </button>
      <button
        onClick={onDelete}
        disabled={isBusy}
        title={
          isDeleteConfirm ? "Click again to confirm delete" : "Delete this rule"
        }
        className={`shrink-0 rounded-lg p-1.5 transition-colors disabled:opacity-40 ${
          isDeleteConfirm
            ? "bg-red-50 text-red-500 hover:bg-red-100"
            : "text-gray-300 hover:bg-red-50 hover:text-red-500"
        }`}
      >
        <Trash2 size={14} />
      </button>
    </div>
  );
}
