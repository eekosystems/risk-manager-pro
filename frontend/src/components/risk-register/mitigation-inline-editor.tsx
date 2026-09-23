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

function payloadFor(text: string) {
  const trimmed = text.trim();
  return { title: trimmed.slice(0, TITLE_MAX), description: trimmed };
}

interface MitigationInlineEditorProps {
  riskId: string;
}

export function MitigationInlineEditor({
  riskId,
}: MitigationInlineEditorProps) {
  const { data: mitigations, isLoading } = useMitigations(riskId);
  const [draft, setDraft] = useState("");
  const { addToast } = useToast();
  const create = useCreateMitigation(riskId);

  function handleAdd() {
    if (!draft.trim()) return;
    create.mutate(payloadFor(draft), {
      onSuccess: () => setDraft(""),
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
        residual risk appears as a proposal to confirm or dismiss.
      </p>
      {isLoading ? (
        <Loader2 size={16} className="animate-spin text-brand-500" />
      ) : (
        <div className="space-y-2">
          {(mitigations ?? []).map((m) => (
            <MitigationRow key={m.id} riskId={riskId} mitigation={m} />
          ))}
        </div>
      )}
      <div className="mt-3 flex items-start gap-2">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add a mitigation or control"
          aria-label="New mitigation"
          rows={2}
          className="min-w-0 flex-1 rounded-lg border border-gray-200 px-3 py-2 text-[13px] focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
        />
        <Button
          size="sm"
          onClick={handleAdd}
          disabled={!draft.trim() || create.isPending}
        >
          <Plus size={14} className="mr-1" />
          Add
        </Button>
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
  const [text, setText] = useState(mitigation.description);
  const { addToast } = useToast();
  const update = useUpdateMitigation(riskId);
  const remove = useDeleteMitigation(riskId);
  const changed =
    text.trim() !== mitigation.description.trim() && text.trim() !== "";

  return (
    <div className="flex items-start gap-2">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        aria-label={`Mitigation: ${mitigation.title}`}
        rows={2}
        className="min-w-0 flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-[13px] focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
      />
      <Button
        size="sm"
        variant="secondary"
        disabled={!changed || update.isPending}
        onClick={() =>
          update.mutate(
            { mitigationId: mitigation.id, payload: payloadFor(text) },
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
