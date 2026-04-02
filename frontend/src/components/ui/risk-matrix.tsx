import { clsx } from "clsx";

import {
  LIKELIHOODS,
  LIKELIHOOD_LABELS,
  RISK_LEVEL_CONFIG,
  RISK_MATRIX,
  SEVERITIES,
  SEVERITY_LABELS,
  type Likelihood,
  type RiskMatrixSelection,
  type RiskPositionCount,
  type Severity,
} from "@/types/risk-matrix";

interface RiskMatrixProps {
  selection: RiskMatrixSelection | null;
  onSelect: (selection: RiskMatrixSelection) => void;
  riskPositions?: RiskPositionCount[];
  readOnly?: boolean;
}

const CELL_COLORS: Record<string, string> = {
  low: "bg-green-200 hover:bg-green-300",
  medium: "bg-yellow-200 hover:bg-yellow-300",
  high: "bg-red-200 hover:bg-red-300",
};

export function RiskMatrix({ selection, onSelect, riskPositions, readOnly }: RiskMatrixProps) {
  const handleCellClick = (likelihood: Likelihood, severity: Severity) => {
    if (readOnly) return;
    const riskLevel = RISK_MATRIX[likelihood][severity];
    onSelect({ severity, likelihood, riskLevel });
  };

  const positionMap = new Map<string, number>();
  if (riskPositions) {
    for (const pos of riskPositions) {
      if (pos.count > 0) {
        positionMap.set(`${pos.likelihood}-${pos.severity}`, pos.count);
      }
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Matrix Grid */}
      <div className="overflow-x-auto">
        <table className="border-collapse">
          <thead>
            <tr>
              <th className="w-36 p-2" />
              {SEVERITIES.map((s) => (
                <th
                  key={s}
                  className="min-w-[72px] p-2 text-center text-xs font-semibold text-gray-600"
                >
                  <div>{SEVERITY_LABELS[s].full}</div>
                  <div className="text-[10px] text-gray-400">({s})</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {LIKELIHOODS.map((l) => (
              <tr key={l}>
                <td className="p-2 text-right text-xs font-semibold text-gray-600">
                  <div>{LIKELIHOOD_LABELS[l].full}</div>
                  <div className="text-[10px] text-gray-400">({l})</div>
                </td>
                {SEVERITIES.map((s) => {
                  const riskLevel = RISK_MATRIX[l][s];
                  const isSelected =
                    selection?.likelihood === l && selection?.severity === s;
                  const count = positionMap.get(`${l}-${s}`);
                  return (
                    <td key={s} className="p-1">
                      <button
                        onClick={() => handleCellClick(l, s)}
                        className={clsx(
                          "relative flex h-14 w-full items-center justify-center rounded-lg border-2 text-xs font-bold transition-all",
                          CELL_COLORS[riskLevel],
                          readOnly ? "cursor-default" : "",
                          isSelected
                            ? "border-gray-900 ring-2 ring-gray-900/20 scale-105"
                            : "border-transparent",
                        )}
                      >
                        {RISK_LEVEL_CONFIG[riskLevel].label}
                        {count != null && (
                          <span className="absolute -right-1 -top-1 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-slate-800 px-1 text-[10px] font-bold text-white shadow-sm">
                            {count}
                          </span>
                        )}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Axis Labels */}
      <div className="flex items-center justify-between px-2 text-[10px] font-bold uppercase tracking-wider text-gray-400">
        <span>Likelihood (rows)</span>
        <span>Severity (columns)</span>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3">
        {(["low", "medium", "high"] as const).map((level) => {
          const cfg = RISK_LEVEL_CONFIG[level];
          return (
            <div key={level} className="flex items-center gap-1.5">
              <div
                className={clsx(
                  "h-3 w-3 rounded-sm border",
                  cfg.bg,
                  cfg.border,
                )}
              />
              <span className="text-xs text-gray-600">{cfg.label}</span>
            </div>
          );
        })}
      </div>

      {/* Selection Summary */}
      {selection && (
        <div
          className={clsx(
            "rounded-lg border p-3",
            RISK_LEVEL_CONFIG[selection.riskLevel].bg,
            RISK_LEVEL_CONFIG[selection.riskLevel].border,
          )}
        >
          <p
            className={clsx(
              "text-sm font-semibold",
              RISK_LEVEL_CONFIG[selection.riskLevel].color,
            )}
          >
            Risk Level: {RISK_LEVEL_CONFIG[selection.riskLevel].label}
          </p>
          <p className="mt-0.5 text-xs text-gray-600">
            Severity: {SEVERITY_LABELS[selection.severity].full} ({selection.severity})
            {" | "}
            Likelihood: {LIKELIHOOD_LABELS[selection.likelihood].full} ({selection.likelihood})
          </p>
        </div>
      )}
    </div>
  );
}
