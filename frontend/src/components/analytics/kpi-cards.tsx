import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  ShieldAlert,
  TrendingUp,
} from "lucide-react";

import type { RiskKPIs } from "@/types/api";

interface KPICardsProps {
  kpis: RiskKPIs;
}

export function KPICards({ kpis }: KPICardsProps) {
  const cards = [
    {
      label: "Total Risks",
      value: kpis.total_risks,
      icon: ShieldAlert,
      color: "text-brand-500",
    },
    {
      label: "Open",
      value: kpis.open_risks,
      icon: AlertTriangle,
      color: "text-blue-500",
    },
    {
      label: "High",
      value: kpis.high_count,
      icon: TrendingUp,
      color: "text-red-500",
    },
    {
      label: "Overdue Mitigations",
      value: kpis.overdue_mitigations,
      icon: Clock,
      color: "text-amber-500",
    },
    {
      label: "Avg Days to Close",
      value: kpis.avg_days_to_close != null ? `${kpis.avg_days_to_close}d` : "--",
      icon: CheckCircle2,
      color: "text-green-500",
    },
  ];

  return (
    <div className="grid grid-cols-5 gap-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.label}
            className="rounded-2xl border border-gray-200 bg-white p-4"
          >
            <div className="flex items-center justify-between">
              <div className={`text-2xl font-bold ${card.color}`}>
                {card.value}
              </div>
              <Icon size={20} className="text-gray-300" />
            </div>
            <div className="mt-1 text-[12px] text-slate-500">{card.label}</div>
          </div>
        );
      })}
    </div>
  );
}
