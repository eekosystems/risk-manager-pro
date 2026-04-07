import { useState } from "react";
import {
  Calendar,
  CheckCircle2,
  Clock,
  Loader2,
  Plus,
  Trash2,
  User,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  useCreateMitigation,
  useDeleteMitigation,
  useUpdateMitigation,
} from "@/hooks/use-risks";
import type { MitigationItem, MitigationStatus } from "@/types/api";

const STATUS_CONFIG: Record<
  MitigationStatus,
  { label: string; icon: typeof Clock; className: string }
> = {
  pending: {
    label: "Pending",
    icon: Clock,
    className: "text-gray-600 bg-gray-100",
  },
  in_progress: {
    label: "In Progress",
    icon: Loader2,
    className: "text-brand-600 bg-brand-50",
  },
  completed: {
    label: "Completed",
    icon: CheckCircle2,
    className: "text-brand-400 bg-brand-50",
  },
  cancelled: {
    label: "Cancelled",
    icon: XCircle,
    className: "text-accent-600 bg-accent-50",
  },
};

const ALL_STATUSES: MitigationStatus[] = [
  "pending",
  "in_progress",
  "completed",
  "cancelled",
];

interface MitigationListProps {
  riskId: string;
  mitigations: MitigationItem[];
}

export function MitigationList({ riskId, mitigations }: MitigationListProps) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newAssignee, setNewAssignee] = useState("");
  const [newDueDate, setNewDueDate] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const createMutation = useCreateMitigation(riskId);
  const updateMutation = useUpdateMitigation(riskId);
  const deleteMutation = useDeleteMitigation(riskId);

  function handleAdd() {
    if (!newTitle.trim() || !newDescription.trim()) return;
    createMutation.mutate(
      {
        title: newTitle.trim(),
        description: newDescription.trim(),
        assignee: newAssignee.trim() || null,
        due_date: newDueDate || null,
      },
      {
        onSuccess: () => {
          setNewTitle("");
          setNewDescription("");
          setNewAssignee("");
          setNewDueDate("");
          setShowAddForm(false);
        },
      },
    );
  }

  function handleStatusChange(mitigationId: string, status: MitigationStatus) {
    updateMutation.mutate({ mitigationId, payload: { status } });
  }

  function handleDelete(mitigationId: string) {
    if (deleteConfirm === mitigationId) {
      deleteMutation.mutate(mitigationId);
      setDeleteConfirm(null);
    } else {
      setDeleteConfirm(mitigationId);
      setTimeout(() => setDeleteConfirm(null), 3000);
    }
  }

  const inputClass =
    "w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-900">
          Mitigations ({mitigations.length})
        </h3>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setShowAddForm(!showAddForm)}
        >
          <Plus size={14} className="mr-1" />
          Add Mitigation
        </Button>
      </div>

      {/* Add form */}
      {showAddForm && (
        <div className="mb-4 rounded-xl border border-brand-200 bg-brand-50/30 p-4">
          <div className="space-y-3">
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="Mitigation title..."
              className={inputClass}
            />
            <textarea
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              placeholder="Describe the mitigation action..."
              className={`${inputClass} min-h-[60px] resize-y`}
            />
            <div className="grid grid-cols-2 gap-3">
              <input
                type="text"
                value={newAssignee}
                onChange={(e) => setNewAssignee(e.target.value)}
                placeholder="Assignee (optional)"
                className={inputClass}
              />
              <input
                type="date"
                value={newDueDate}
                onChange={(e) => setNewDueDate(e.target.value)}
                className={inputClass}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowAddForm(false)}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleAdd}
                disabled={
                  createMutation.isPending ||
                  !newTitle.trim() ||
                  !newDescription.trim()
                }
              >
                {createMutation.isPending ? (
                  <Loader2 size={14} className="mr-1 animate-spin" />
                ) : null}
                Add
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Mitigation list */}
      {mitigations.length === 0 ? (
        <div className="rounded-xl border border-gray-200 bg-white p-6 text-center text-sm text-gray-400">
          No mitigations yet. Add one to track corrective actions.
        </div>
      ) : (
        <div className="space-y-3">
          {mitigations.map((m) => {
            const statusCfg = STATUS_CONFIG[m.status];
            const StatusIcon = statusCfg.icon;
            return (
              <div
                key={m.id}
                className="rounded-xl border border-gray-200 bg-white p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-slate-800">
                        {m.title}
                      </span>
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${statusCfg.className}`}
                      >
                        <StatusIcon size={10} />
                        {statusCfg.label}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {m.description}
                    </p>
                    <div className="mt-2 flex items-center gap-4 text-[11px] text-slate-400">
                      {m.assignee && (
                        <span className="flex items-center gap-1">
                          <User size={10} />
                          {m.assignee}
                        </span>
                      )}
                      {m.due_date && (
                        <span className="flex items-center gap-1">
                          <Calendar size={10} />
                          {new Date(m.due_date).toLocaleDateString()}
                        </span>
                      )}
                      {m.completed_at && (
                        <span className="flex items-center gap-1">
                          <CheckCircle2 size={10} />
                          Completed{" "}
                          {new Date(m.completed_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <select
                      value={m.status}
                      onChange={(e) =>
                        handleStatusChange(
                          m.id,
                          e.target.value as MitigationStatus,
                        )
                      }
                      className="rounded-lg border border-gray-200 px-2 py-1 text-xs text-slate-600 focus:border-brand-500 focus:outline-none"
                    >
                      {ALL_STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {STATUS_CONFIG[s].label}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => handleDelete(m.id)}
                      className={`rounded-lg p-1.5 transition-colors ${
                        deleteConfirm === m.id
                          ? "bg-red-50 text-red-500"
                          : "text-gray-300 hover:bg-red-50 hover:text-red-500"
                      }`}
                      title={
                        deleteConfirm === m.id
                          ? "Click again to confirm"
                          : "Delete mitigation"
                      }
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
