"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ScoreRow } from "@/lib/queries";

const SERIES = [
  { key: "overallScore", label: "Overall", color: "#0f172a" },
  { key: "calorieScore", label: "Calories", color: "#ef4444" },
  { key: "proteinScore", label: "Protein", color: "#f59e0b" },
  { key: "activityScore", label: "Activity", color: "#10b981" },
  { key: "waterScore", label: "Water", color: "#3b82f6" },
  { key: "consistencyScore", label: "Consistency", color: "#8b5cf6" },
] as const;

export function ScoreBreakdownChart({ data }: { data: ScoreRow[] }) {
  return (
    <div className="mt-4 h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="scoreDate" tick={{ fontSize: 12 }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Legend />
          {SERIES.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
