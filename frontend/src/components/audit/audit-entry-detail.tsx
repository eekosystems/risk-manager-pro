import type { AuditEntry } from "@/types/api";

/** Keys shown elsewhere on the row, or too long to be useful inline. */
const HIDDEN_KEYS = new Set(["conversation_id", "updated_fields"]);

interface Change {
  old: unknown;
  new: unknown;
}

function isChange(value: unknown): value is Change {
  return typeof value === "object" && value !== null && "old" in value && "new" in value;
}

function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "none";
  if (Array.isArray(value)) return value.map(show).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

interface AuditEntryDetailProps {
  metadata: AuditEntry["metadata"];
}

/** Before/after values and other detail an audit row carries, under its action. */
export function AuditEntryDetail({ metadata }: AuditEntryDetailProps) {
  if (!metadata) return null;
  const changes = metadata.changes;
  const changeRows =
    typeof changes === "object" && changes !== null
      ? Object.entries(changes as Record<string, unknown>).filter(([, v]) => isChange(v))
      : [];
  const otherRows = Object.entries(metadata).filter(
    ([key, value]) =>
      key !== "changes" && !HIDDEN_KEYS.has(key) && value !== null && value !== undefined,
  );
  if (changeRows.length === 0 && otherRows.length === 0) return null;

  return (
    <dl className="mt-1 space-y-0.5 text-[11px] font-normal text-slate-500">
      {changeRows.map(([field, change]) => (
        <div key={field} className="flex flex-wrap gap-x-1">
          <dt className="font-medium text-slate-600">{field}:</dt>
          <dd>
            <span className="line-through">{show((change as Change).old)}</span>{" "}
            <span className="text-slate-700">{show((change as Change).new)}</span>
          </dd>
        </div>
      ))}
      {otherRows.map(([key, value]) => (
        <div key={key} className="flex flex-wrap gap-x-1">
          <dt className="font-medium text-slate-600">{key}:</dt>
          <dd>{show(value)}</dd>
        </div>
      ))}
    </dl>
  );
}
