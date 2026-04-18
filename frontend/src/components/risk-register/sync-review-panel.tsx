import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, RefreshCw, X } from "lucide-react";
import { useState } from "react";

import {
  acceptPendingChange,
  listPendingSyncChanges,
  rejectPendingChange,
  type PendingSyncChange,
} from "@/api/rr-sync";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

/**
 * Sync review queue — surfaced both in the Faith Group RR (incoming changes
 * from client airports) and in a Client RR (incoming changes from FG).
 * Every dual-record edit lands here as a pending diff; nothing auto-applies.
 */
export function SyncReviewPanel() {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["rr-sync-queue", "pending"],
    queryFn: () => listPendingSyncChanges("pending"),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="animate-spin text-brand-500" size={22} />
      </div>
    );
  }

  const items = data ?? [];

  return (
    <div className="mx-auto max-w-4xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Sync Review Queue</h2>
          <p className="text-sm text-slate-500">
            Dual-record changes from the counterpart Risk Register awaiting review.
            Nothing is applied until you accept.
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          <RefreshCw
            size={14}
            className={`mr-2 ${isFetching ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
      </div>

      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-200 bg-white p-10 text-center text-sm text-slate-500">
          No pending sync changes.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <SyncChangeCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}

function SyncChangeCard({ item }: { item: PendingSyncChange }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [note, setNote] = useState("");

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["rr-sync-queue"] });
    void queryClient.invalidateQueries({ queryKey: ["risks"] });
  };

  const acceptMut = useMutation({
    mutationFn: () => acceptPendingChange(item.id, note || undefined),
    onSuccess: () => {
      addToast("Change accepted", "success");
      invalidate();
    },
    onError: (err: Error) => addToast(`Accept failed: ${err.message}`, "error"),
  });

  const rejectMut = useMutation({
    mutationFn: () => rejectPendingChange(item.id, note || undefined),
    onSuccess: () => {
      addToast("Change rejected", "success");
      invalidate();
    },
    onError: (err: Error) => addToast(`Reject failed: ${err.message}`, "error"),
  });

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-semibold uppercase text-brand-600">
            {item.change_type}
          </span>
          <span className="text-[11px] uppercase text-slate-400">
            {item.direction === "client_to_fg" ? "Client → FG" : "FG → Client"}
          </span>
        </div>
        <span className="text-[11px] text-slate-400">
          {new Date(item.created_at).toLocaleString()}
        </span>
      </div>
      <DiffPreview diffJson={item.diff_json} changeType={item.change_type} />
      <div className="mt-3 flex items-center gap-2">
        <input
          type="text"
          placeholder="Optional note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className="flex-1 rounded-lg border border-gray-200 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
        />
        <Button
          onClick={() => acceptMut.mutate()}
          disabled={acceptMut.isPending || rejectMut.isPending}
        >
          <Check size={14} className="mr-1" />
          Accept
        </Button>
        <Button
          variant="secondary"
          onClick={() => rejectMut.mutate()}
          disabled={acceptMut.isPending || rejectMut.isPending}
        >
          <X size={14} className="mr-1" />
          Reject
        </Button>
      </div>
    </div>
  );
}

function DiffPreview({
  diffJson,
  changeType,
}: {
  diffJson: Record<string, unknown>;
  changeType: string;
}) {
  if (changeType === "create") {
    const create = (diffJson.create ?? {}) as Record<string, unknown>;
    const fields: Array<[string, unknown]> = Object.entries(create).filter(
      ([, v]) => v !== null && v !== "",
    );
    return (
      <div className="rounded-lg bg-gray-50 p-3">
        <div className="mb-1.5 text-[11px] font-semibold uppercase text-slate-500">
          New record proposed
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-[12px]">
          {fields.slice(0, 12).map(([k, v]) => (
            <div key={k} className="flex flex-col">
              <dt className="text-slate-400">{k}</dt>
              <dd className="text-slate-700 break-all">{String(v)}</dd>
            </div>
          ))}
        </dl>
      </div>
    );
  }

  const update = (diffJson.update ?? {}) as Record<
    string,
    { old: unknown; new: unknown }
  >;
  return (
    <div className="rounded-lg bg-gray-50 p-3">
      <div className="mb-1.5 text-[11px] font-semibold uppercase text-slate-500">
        Field changes
      </div>
      <table className="w-full text-[12px]">
        <thead className="text-slate-400">
          <tr>
            <th className="pb-1 text-left">Field</th>
            <th className="pb-1 text-left">Before</th>
            <th className="pb-1 text-left">After</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(update).map(([field, change]) => (
            <tr key={field} className="border-t border-gray-100">
              <td className="py-1 pr-4 text-slate-500">{field}</td>
              <td className="py-1 pr-4 text-slate-600 line-through">
                {String(change.old ?? "—")}
              </td>
              <td className="py-1 text-slate-900">
                {String(change.new ?? "—")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
