import { useState } from "react";
import { Loader2, Plus, Save, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  useCreateMitigation,
  useDeleteMitigation,
  useMitigations,
  useUpdateMitigation,
} from "@/hooks/use-risks";
import { useToast } from "@/hooks/use-toast";
import type { MitigationItem } from "@/types/api";

// Mitigation titles are capped server-side; the full text lives in the description.
const TITLE_MAX = 500;

const FIELD_CLASS =
  "min-w-0 rounded-lg border border-gray-200 bg-white px-3 py-2 text-[13px] focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

interface MitigationDraft {
  text: string;
  assignee: string;
  /** YYYY-MM-DD, as the date input holds it; empty when unset. */
  dueDate: string;
}

const EMPTY_DRAFT: MitigationDraft = { text: "", assignee: "", dueDate: "" };

function draftFor(m: MitigationItem): MitigationDraft {
  return {
    text: m.description,
    assignee: m.assignee ?? "",
    dueDate: m.due_date ? m.due_date.slice(0, 10) : "",
  };
}

/** Empty owner and date clear the saved values; the backend treats null as "none". */
function payloadFor(draft: MitigationDraft) {
  const trimmed = draft.text.trim();
  return {
    title: trimmed.slice(0, TITLE_MAX),
    description: trimmed,
    assignee: draft.assignee.trim() || null,
    due_date: draft.dueDate || null,
  };
}

function sameDraft(a: MitigationDraft, b: MitigationDraft): boolean {
  return (
    a.text.trim() === b.text.trim() &&
    a.assignee.trim() === b.assignee.trim() &&
    a.dueDate === b.dueDate
  );
}

interface MitigationInlineEditorProps {
  riskId: string;
}

export function MitigationInlineEditor({
  riskId,
}: MitigationInlineEditorProps) {
  const { data: mitigations, isLoading } = useMitigations(riskId);
  const [draft, setDraft] = useState<MitigationDraft>(EMPTY_DRAFT);
  const { addToast } = useToast();
  const create = useCreateMitigation(riskId);

  function handleAdd() {
    if (!draft.text.trim()) return;
    create.mutate(payloadFor(draft), {
      onSuccess: () => setDraft(EMPTY_DRAFT),
      onError: () => addToast("Could not add the mitigation", "error"),
    });
  }

  return (
    <div
      className="border-t border-dashed border-gray-200 bg-gray-50/70 px-5 py-4"
      onClick={(e) => e.stopPropagation()}
    >
      <p className="mb-3 text-[11px] text-slate-500">
        Saving a change re-runs the SRA assessment for this hazard. The new
        residual risk appears as a proposal to confirm or dismiss. Leave the
        owner or due date blank to clear it.
      </p>
      {isLoading ? (
        <Loader2 size={16} className="animate-spin text-brand-500" />
      ) : (
        <div className="space-y-3">
          {(mitigations ?? []).map((m) => (
            <MitigationRow key={m.id} riskId={riskId} mitigation={m} />
          ))}
        </div>
      )}
      <div className="mt-3 flex items-start gap-2">
        <MitigationFields
          draft={draft}
          onChange={setDraft}
          label="New mitigation"
          placeholder="Add a mitigation or control"
        />
        <Button
          size="sm"
          onClick={handleAdd}
          disabled={!draft.text.trim() || create.isPending}
        >
          <Plus size={14} className="mr-1" />
          Add
        </Button>
      </div>
    </div>
  );
}

function MitigationFields({
  draft,
  onChange,
  label,
  placeholder,
}: {
  draft: MitigationDraft;
  onChange: (draft: MitigationDraft) => void;
  label: string;
  placeholder?: string;
}) {
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-2">
      <textarea
        value={draft.text}
        onChange={(e) => onChange({ ...draft, text: e.target.value })}
        placeholder={placeholder}
        aria-label={label}
        rows={2}
        className={FIELD_CLASS}
      />
      <div className="flex flex-wrap gap-2">
        <input
          type="text"
          value={draft.assignee}
          onChange={(e) => onChange({ ...draft, assignee: e.target.value })}
          placeholder="Owner"
          aria-label={`${label} owner`}
          className={`${FIELD_CLASS} flex-1`}
        />
        <input
          type="date"
          value={draft.dueDate}
          onChange={(e) => onChange({ ...draft, dueDate: e.target.value })}
          aria-label={`${label} due date`}
          className={FIELD_CLASS}
        />
      </div>
    </div>
  );
}

function MitigationRow({
  riskId,
  mitigation,
}: {
  riskId: string;
  mitigation: MitigationItem;
}) {
  const saved = draftFor(mitigation);
  const [draft, setDraft] = useState<MitigationDraft>(saved);
  const { addToast } = useToast();
  const update = useUpdateMitigation(riskId);
  const remove = useDeleteMitigation(riskId);
  const changed = !sameDraft(draft, saved) && draft.text.trim() !== "";

  return (
    <div className="flex items-start gap-2">
      <MitigationFields
        draft={draft}
        onChange={setDraft}
        label={`Mitigation: ${mitigation.title}`}
      />
      <Button
        size="sm"
        variant="secondary"
        disabled={!changed || update.isPending}
        onClick={() =>
          update.mutate(
            { mitigationId: mitigation.id, payload: payloadFor(draft) },
            {
              onError: () => addToast("Could not save the mitigation", "error"),
            },
          )
        }
      >
        <Save size={14} className="mr-1" />
        Save
      </Button>
      <Button
        size="sm"
        variant="danger"
        aria-label={`Delete mitigation: ${mitigation.title}`}
        disabled={remove.isPending}
        onClick={() =>
          remove.mutate(mitigation.id, {
            onError: () => addToast("Could not delete the mitigation", "error"),
          })
        }
      >
        <Trash2 size={14} />
      </Button>
    </div>
  );
}
