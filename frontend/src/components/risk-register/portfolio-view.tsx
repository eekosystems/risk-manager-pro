import { useQuery } from "@tanstack/react-query";
import { Loader2, RefreshCw } from "lucide-react";
import { useState } from "react";

import { getPortfolio, type PortfolioRiskRow } from "@/api/rr-sync";
import { Button } from "@/components/ui/button";
import { RISK_LEVEL_CONFIG, type RiskLevel } from "@/types/risk-matrix";

/**
 * Faith Group portfolio roll-up across every client organization.
 * Platform-admin only (backend enforces). Default view sorts most-recent first,
 * grouped visually by airport via the Airport column.
 */
export function PortfolioView() {
  const [airportFilter, setAirportFilter] = useState("");
  const [riskLevelFilter, setRiskLevelFilter] = useState<string>("");

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["rr-portfolio", airportFilter, riskLevelFilter],
    queryFn: () => {
      const params: { airport_identifier?: string; risk_level?: string } = {};
      if (airportFilter) params.airport_identifier = airportFilter;
      if (riskLevelFilter) params.risk_level = riskLevelFilter;
      return getPortfolio(params);
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="animate-spin text-brand-500" size={22} />
      </div>
    );
  }

  const rows = data ?? [];

  return (
    <div className="mx-auto max-w-7xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-900">FG Portfolio View</h2>
          <p className="text-sm text-slate-500">
            Cross-airport risk roll-up across every client organization.
          </p>
        </div>
        <Button variant="secondary" onClick={() => refetch()} disabled={isFetching}>
          <RefreshCw
            size={14}
            className={`mr-2 ${isFetching ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
      </div>

      <div className="mb-3 flex gap-3">
        <input
          type="text"
          placeholder="Filter by airport (e.g., KSFO)"
          value={airportFilter}
          onChange={(e) => setAirportFilter(e.target.value.toUpperCase())}
          className="w-60 rounded-lg border border-gray-200 px-3 py-1.5 text-sm font-mono focus:border-brand-500 focus:outline-none"
        />
        <select
          value={riskLevelFilter}
          onChange={(e) => setRiskLevelFilter(e.target.value)}
          className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
        >
          <option value="">All risk levels</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="extreme">Extreme</option>
        </select>
        <span className="ml-auto self-center text-sm text-slate-500">
          {rows.length} records
        </span>
      </div>

      {rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-200 bg-white p-10 text-center text-sm text-slate-500">
          No records match the current filters.
        </div>
      ) : (
        <div className="overflow-auto rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-[11px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left">Airport</th>
                <th className="px-3 py-2 text-left">Organization</th>
                <th className="px-3 py-2 text-left">Title</th>
                <th className="px-3 py-2 text-left">Risk</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Validation</th>
                <th className="px-3 py-2 text-left">Source</th>
                <th className="px-3 py-2 text-left">Updated</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <PortfolioRow key={r.id} row={r} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function PortfolioRow({ row }: { row: PortfolioRiskRow }) {
  const levelCfg = RISK_LEVEL_CONFIG[row.risk_level as RiskLevel] ?? RISK_LEVEL_CONFIG.low;
  return (
    <tr className="border-t border-gray-100 hover:bg-gray-50">
      <td className="px-3 py-2 font-mono text-slate-700">
        {row.airport_identifier ?? "—"}
      </td>
      <td className="px-3 py-2 text-slate-600">{row.organization_name}</td>
      <td className="px-3 py-2 text-slate-800">{row.title}</td>
      <td className="px-3 py-2">
        <span
          className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${levelCfg.bg} ${levelCfg.color}`}
        >
          {levelCfg.label}
        </span>
      </td>
      <td className="px-3 py-2 text-slate-600 capitalize">
        {row.record_status.replace(/_/g, " ")}
      </td>
      <td className="px-3 py-2 text-slate-600 capitalize">
        {row.validation_status.replace(/_/g, " ")}
      </td>
      <td className="px-3 py-2 text-slate-500 text-[12px] capitalize">
        {row.source.replace(/_/g, " ")}
      </td>
      <td className="px-3 py-2 text-slate-500 text-[12px]">
        {new Date(row.updated_at).toLocaleDateString()}
      </td>
    </tr>
  );
}
