import { Pencil } from "lucide-react";

import type { MitigationSummary } from "@/types/api";

const VISIBLE_MITIGATIONS = 3;

interface MitigationsCellProps {
  mitigations: MitigationSummary[];
  /** Null when the row cannot be edited (viewer, or not yet imported). */
  onEdit: (() => void) | null;
  editing: boolean;
  hint: string | null;
}

export function MitigationsCell({
  mitigations,
  onEdit,
  editing,
  hint,
}: MitigationsCellProps) {
  const hidden = mitigations.length - VISIBLE_MITIGATIONS;
  return (
    <div className="min-w-0 space-y-1" onClick={(e) => e.stopPropagation()}>
      {mitigations.length === 0 ? (
        <span className="text-[11px] italic text-slate-400">None recorded</span>
      ) : (
        <ul className="space-y-0.5">
          {mitigations.slice(0, VISIBLE_MITIGATIONS).map((m) => (
            <li
              key={m.id}
              className="truncate text-[11px] text-slate-600"
              title={m.title}
            >
              • {m.title}
            </li>
          ))}
          {hidden > 0 && (
            <li className="text-[11px] text-slate-400">+{hidden} more</li>
          )}
        </ul>
      )}
      {onEdit && (
        <button
          onClick={onEdit}
          className="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-semibold text-brand-600 hover:bg-brand-50"
        >
          <Pencil size={10} />
          {editing ? "Close editor" : "Edit mitigations"}
        </button>
      )}
      {hint && <p className="text-[10px] italic text-slate-400">{hint}</p>}
    </div>
  );
}
