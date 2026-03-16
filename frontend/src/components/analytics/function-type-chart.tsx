import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { RisksByFunctionTypeItem } from "@/types/api";

interface FunctionTypeChartProps {
  data: RisksByFunctionTypeItem[];
}

const FUNCTION_LABELS: Record<string, string> = {
  phl: "PHL",
  sra: "SRA",
  system: "System",
  general: "General",
};

export function FunctionTypeChart({ data }: FunctionTypeChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-400">
        No data yet
      </div>
    );
  }

  const chartData = data.map((d) => ({
    name: FUNCTION_LABELS[d.function_type] ?? d.function_type,
    count: d.count,
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis
          dataKey="name"
          tick={{ fontSize: 11, fill: "#94a3b8" }}
          tickLine={false}
          axisLine={{ stroke: "#e2e8f0" }}
        />
        <YAxis
          allowDecimals={false}
          tick={{ fontSize: 11, fill: "#94a3b8" }}
          tickLine={false}
          axisLine={{ stroke: "#e2e8f0" }}
        />
        <Tooltip
          contentStyle={{
            borderRadius: 12,
            border: "1px solid #e2e8f0",
            fontSize: 12,
          }}
        />
        <Bar dataKey="count" fill="#6366f1" radius={[6, 6, 0, 0]} name="Risks" />
      </BarChart>
    </ResponsiveContainer>
  );
}
