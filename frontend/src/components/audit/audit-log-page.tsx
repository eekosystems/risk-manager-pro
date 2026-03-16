import { format } from "date-fns";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  Loader2,
  Search,
  ShieldCheck,
} from "lucide-react";
import { useCallback, useState } from "react";

import { exportAuditCsv, type GetAuditParams } from "@/api/audit";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useAuditEntries, useAuditFilterOptions } from "@/hooks/use-audit";
import { useToast } from "@/hooks/use-toast";

const ACTION_LABELS: Record<string, string> = {
  "risk.created": "Risk Created",
  "risk.updated": "Risk Updated",
  "risk.deleted": "Risk Deleted",
  "mitigation.created": "Mitigation Added",
  "mitigation.updated": "Mitigation Updated",
  "mitigation.deleted": "Mitigation Deleted",
  "message_sent": "Message Sent",
  "conversation_deleted": "Conversation Deleted",
  "document.uploaded": "Document Uploaded",
  "document.deleted": "Document Deleted",
  "organization.created": "Org Created",
  "organization.updated": "Org Updated",
  "member_added": "Member Added",
  "member_role_updated": "Role Updated",
  "member_removed": "Member Removed",
  "rag.updated": "RAG Settings Updated",
  "model.updated": "Model Settings Updated",
  "prompts.updated": "Prompts Updated",
  "user.auto_provisioned": "User Provisioned",
};

const OUTCOME_STYLES: Record<string, string> = {
  success: "bg-green-50 text-green-600",
  failure: "bg-red-50 text-red-600",
  denied: "bg-amber-50 text-amber-600",
};

const PAGE_SIZE = 25;

export function AuditLogPage() {
  const [page, setPage] = useState(0);
  const [actionFilter, setActionFilter] = useState("");
  const [resourceTypeFilter, setResourceTypeFilter] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [isExporting, setIsExporting] = useState(false);
  const { addToast } = useToast();

  const params: GetAuditParams = {
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    ...(actionFilter ? { action: actionFilter } : {}),
    ...(resourceTypeFilter ? { resource_type: resourceTypeFilter } : {}),
    ...(outcomeFilter ? { outcome: outcomeFilter } : {}),
    ...(dateFrom ? { date_from: new Date(dateFrom).toISOString() } : {}),
    ...(dateTo ? { date_to: new Date(dateTo + "T23:59:59").toISOString() } : {}),
  };

  const { data, isLoading } = useAuditEntries(params);
  const { data: filterOptions } = useAuditFilterOptions();

  const entries = data?.data ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.total_pages ?? 0;

  const handleExport = useCallback(async () => {
    setIsExporting(true);
    try {
      await exportAuditCsv({
        ...(actionFilter ? { action: actionFilter } : {}),
        ...(resourceTypeFilter ? { resource_type: resourceTypeFilter } : {}),
        ...(outcomeFilter ? { outcome: outcomeFilter } : {}),
        ...(dateFrom ? { date_from: new Date(dateFrom).toISOString() } : {}),
        ...(dateTo ? { date_to: new Date(dateTo + "T23:59:59").toISOString() } : {}),
      });
      addToast("Audit log exported", "success");
    } catch {
      addToast("Failed to export audit log", "error");
    } finally {
      setIsExporting(false);
    }
  }, [actionFilter, resourceTypeFilter, outcomeFilter, dateFrom, dateTo, addToast]);

  const resetFilters = useCallback(() => {
    setActionFilter("");
    setResourceTypeFilter("");
    setOutcomeFilter("");
    setDateFrom("");
    setDateTo("");
    setPage(0);
  }, []);

  const selectClass =
    "rounded-xl border border-gray-200 px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

  const hasFilters = actionFilter || resourceTypeFilter || outcomeFilter || dateFrom || dateTo;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-6xl p-6">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck size={20} className="text-brand-500" />
              <h2 className="text-lg font-bold text-slate-900">
                Audit Log
              </h2>
            </div>
            <p className="mt-0.5 text-xs text-slate-400">
              {total} total entries
            </p>
          </div>
          <Button
            variant="secondary"
            onClick={handleExport}
            disabled={isExporting || total === 0}
          >
            {isExporting ? (
              <Loader2 size={16} className="mr-2 animate-spin" />
            ) : (
              <Download size={16} className="mr-2" />
            )}
            Export CSV
          </Button>
        </div>

        {/* Filters */}
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <select
            value={actionFilter}
            onChange={(e) => { setActionFilter(e.target.value); setPage(0); }}
            className={selectClass}
          >
            <option value="">All Actions</option>
            {filterOptions?.actions.map((a) => (
              <option key={a} value={a}>
                {ACTION_LABELS[a] ?? a}
              </option>
            ))}
          </select>

          <select
            value={resourceTypeFilter}
            onChange={(e) => { setResourceTypeFilter(e.target.value); setPage(0); }}
            className={selectClass}
          >
            <option value="">All Resource Types</option>
            {filterOptions?.resource_types.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>

          <select
            value={outcomeFilter}
            onChange={(e) => { setOutcomeFilter(e.target.value); setPage(0); }}
            className={selectClass}
          >
            <option value="">All Outcomes</option>
            {filterOptions?.outcomes.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>

          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(0); }}
            className={selectClass}
            title="From date"
          />
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(0); }}
            className={selectClass}
            title="To date"
          />

          {hasFilters && (
            <button
              onClick={resetFilters}
              className="text-xs font-medium text-brand-500 hover:text-brand-600"
            >
              Clear filters
            </button>
          )}
        </div>

        {/* Table */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 size={24} className="animate-spin text-brand-500" />
          </div>
        ) : entries.length === 0 ? (
          <EmptyState
            icon={Search}
            title="No audit entries found"
            description={
              hasFilters
                ? "Try adjusting your filters"
                : "Audit entries will appear here as actions are performed"
            }
          />
        ) : (
          <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50">
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-gray-400">
                    Timestamp
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-gray-400">
                    Action
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-gray-400">
                    Resource
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-gray-400">
                    Outcome
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-gray-400">
                    IP Address
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-gray-400">
                    User ID
                  </th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry, i) => {
                  const outcomeCls =
                    OUTCOME_STYLES[entry.outcome] ?? OUTCOME_STYLES.success;
                  return (
                    <tr
                      key={entry.id}
                      className={`transition-colors hover:bg-gray-50 ${
                        i < entries.length - 1 ? "border-b border-gray-100" : ""
                      }`}
                    >
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                        {format(new Date(entry.timestamp), "MMM d, yyyy HH:mm:ss")}
                      </td>
                      <td className="px-4 py-3 text-sm font-medium text-slate-800">
                        {ACTION_LABELS[entry.action] ?? entry.action}
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-slate-500">
                          {entry.resource_type}
                        </span>
                        {entry.resource_id && (
                          <span className="ml-1 text-[10px] text-slate-400" title={entry.resource_id}>
                            ({entry.resource_id.slice(0, 8)}...)
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${outcomeCls}`}
                        >
                          {entry.outcome}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-400">
                        {entry.ip_address}
                      </td>
                      <td className="px-4 py-3 text-[10px] text-slate-400" title={entry.user_id}>
                        {entry.user_id.slice(0, 8)}...
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between border-t border-gray-100 px-4 py-3">
                <span className="text-xs text-slate-400">
                  Page {page + 1} of {totalPages}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="rounded-lg border border-gray-200 p-1.5 text-gray-400 transition-colors hover:bg-gray-50 hover:text-gray-600 disabled:opacity-40"
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                    disabled={page >= totalPages - 1}
                    className="rounded-lg border border-gray-200 p-1.5 text-gray-400 transition-colors hover:bg-gray-50 hover:text-gray-600 disabled:opacity-40"
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
