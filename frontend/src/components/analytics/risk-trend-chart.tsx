import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { RiskLevelTimeSeries } from "@/types/api";

interface RiskTrendChartProps {
  data: RiskLevelTimeSeries[];
}

const LEVEL_COLORS = {
  high: "#ef4444",
  medium: "#eab308",
  low: "#22c55e",
};

export function RiskTrendChart({ data }: RiskTrendChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-400">
        No trend data yet
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis
          dataKey="month"
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
        <Legend
          iconType="circle"
          iconSize={8}
          wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
        />
        <Area
          type="monotone"
          dataKey="high"
          stackId="1"
          stroke={LEVEL_COLORS.high}
          fill={LEVEL_COLORS.high}
          fillOpacity={0.6}
          name="High"
        />
        <Area
          type="monotone"
          dataKey="medium"
          stackId="1"
          stroke={LEVEL_COLORS.medium}
          fill={LEVEL_COLORS.medium}
          fillOpacity={0.6}
          name="Medium"
        />
        <Area
          type="monotone"
          dataKey="low"
          stackId="1"
          stroke={LEVEL_COLORS.low}
          fill={LEVEL_COLORS.low}
          fillOpacity={0.6}
          name="Low"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
