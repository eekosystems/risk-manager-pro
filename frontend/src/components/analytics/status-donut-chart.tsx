import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import type { RiskStatusBreakdownItem } from "@/types/api";

interface StatusDonutChartProps {
  data: RiskStatusBreakdownItem[];
}

const STATUS_COLORS: Record<string, string> = {
  open: "#4A9BA5",
  mitigating: "#C4A73D",
  closed: "#8DD4DC",
  accepted: "#316670",
};

const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  mitigating: "Mitigating",
  closed: "Closed",
  accepted: "Accepted",
};

export function StatusDonutChart({ data }: StatusDonutChartProps) {
  const total = data.reduce((sum, d) => sum + d.count, 0);

  if (total === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-400">
        No data yet
      </div>
    );
  }

  const chartData = data.map((d) => ({
    name: STATUS_LABELS[d.status] ?? d.status,
    value: d.count,
    status: d.status,
  }));

  return (
    <div className="flex flex-col items-center">
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={85}
            paddingAngle={3}
            dataKey="value"
            nameKey="name"
            stroke="none"
          >
            {chartData.map((entry) => (
              <Cell
                key={entry.status}
                fill={STATUS_COLORS[entry.status] ?? "#94a3b8"}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              borderRadius: 12,
              border: "1px solid #e2e8f0",
              fontSize: 12,
            }}
          />
        </PieChart>
      </ResponsiveContainer>
      {/* Legend */}
      <div className="flex flex-wrap justify-center gap-3">
        {chartData.map((entry) => (
          <div key={entry.status} className="flex items-center gap-1.5">
            <div
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: STATUS_COLORS[entry.status] ?? "#94a3b8" }}
            />
            <span className="text-[11px] text-slate-600">
              {entry.name} ({entry.value})
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
