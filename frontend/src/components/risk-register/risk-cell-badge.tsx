import {
  formatCell,
  RISK_LEVEL_CONFIG,
  type RiskLevel,
} from "@/types/risk-matrix";

interface RiskCellBadgeProps {
  likelihood: string | null;
  severity: number | null;
  level: string | null;
  emptyLabel?: string;
}

/** A matrix cell ("C2") with its band, as the register shows initial and residual risk. */
export function RiskCellBadge({
  likelihood,
  severity,
  level,
  emptyLabel = "Not recorded",
}: RiskCellBadgeProps) {
  const levelCfg = level ? RISK_LEVEL_CONFIG[level as RiskLevel] : undefined;
  if (!levelCfg) {
    return (
      <span className="text-[11px] italic text-slate-400">{emptyLabel}</span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5">
      {likelihood && severity !== null && (
        <span className="font-mono text-[11px] font-bold text-slate-600">
          {formatCell(likelihood, severity)}
        </span>
      )}
      <span
        className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${levelCfg.bg} ${levelCfg.color}`}
      >
        {levelCfg.label}
      </span>
    </span>
  );
}
