"use client";

import useSWR from "swr";
import { fetcher, BASE_URL } from "@/services/api";
import { useDashboardFilter } from "@/context/DashboardFilterContext";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from "recharts";

interface TimelineItem {
  date: string;
  count: number;
}

interface TimelineData {
  timeline: TimelineItem[];
}

function ChartSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-border p-6">
      <div className="h-6 w-48 bg-gray-200 rounded mb-6 animate-pulse" />
      <div className="h-64 bg-gray-200 rounded animate-pulse" />
    </div>
  );
}

export default function TimelineChart() {
  const { queryString } = useDashboardFilter();
  const { data, error, isLoading } = useSWR<TimelineData>(
    `${BASE_URL}/timeline${queryString}`,
    fetcher
  );

  if (isLoading) {
    return <ChartSkeleton />;
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-xl border border-border p-6">
        <p className="text-destructive">Error loading timeline data</p>
      </div>
    );
  }

  const chartData = (data?.timeline ?? []).map((item) => ({
    ...item,
    date: new Date(item.date).toLocaleDateString("id-ID", {
      day: "numeric",
      month: "short",
    }),
  }));

  return (
    <div className="bg-white rounded-xl border border-border p-6">
      <h3 className="text-lg font-semibold text-black mb-6">
        Timeline of Mentions
      </h3>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
            <XAxis
              dataKey="date"
              stroke="#374151"
              fontSize={12}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="#374151"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#ffffff",
                border: "1px solid #e5e7eb",
                borderRadius: "8px",
                color: "#111111",
              }}
              labelStyle={{ color: "#374151" }}
            />
            <Area
              type="monotone"
              dataKey="count"
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#colorCount)"
              name="Mentions"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}