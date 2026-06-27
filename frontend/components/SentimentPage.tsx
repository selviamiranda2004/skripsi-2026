"use client";

import useSWR from "swr";
import { fetcher, BASE_URL } from "@/services/api";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";

interface Mention {
  id: number;
  title: string;
  author: string;
  date: string;
  sentiment: "positif" | "negatif" | "netral";
  source: string;
}

interface SentimentBreakdownData {
  breakdown: {
    positif: Mention[];
    negatif: Mention[];
    netral: Mention[];
  };
  counts: {
    positif: number;
    negatif: number;
    netral: number;
  };
}

function PageSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-8 w-48 bg-gray-200 rounded animate-pulse" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="h-80 bg-white border border-border rounded-xl animate-pulse" />
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 bg-white border border-border rounded-xl animate-pulse" />
          ))}
        </div>
      </div>
    </div>
  );
}

const COLORS = {
  positif: "#22c55e",
  negatif: "#ef4444",
  netral: "#71717a",
};

const ICONS = {
  positif: TrendingUp,
  negatif: TrendingDown,
  netral: Minus,
};

const LABELS = {
  positif: "Positif",
  negatif: "Negatif",
  netral: "Netral",
};

export default function SentimentPage() {
  const { data, error, isLoading } = useSWR<SentimentBreakdownData>(
    `${BASE_URL}/sentiment-breakdown`,
    fetcher
  );

  if (isLoading) {
    return <PageSkeleton />;
  }

  if (error || !data) {
    return (
      <div className="bg-destructive/10 text-destructive rounded-xl p-4">
        Error loading sentiment data
      </div>
    );
  }

  const pieData = [
    { name: "Positif", value: data.counts.positif, color: COLORS.positif },
    { name: "Negatif", value: data.counts.negatif, color: COLORS.negatif },
    { name: "Netral", value: data.counts.netral, color: COLORS.netral },
  ];

  const total = data.counts.positif + data.counts.negatif + data.counts.netral;

  return (
    <div>
      <h2 className="text-2xl font-bold text-black mb-6">
        Sentiment Analysis
      </h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Pie Chart */}
        <div className="bg-white rounded-xl border border-border p-6">
          <h3 className="text-lg font-semibold text-black mb-4">
            Sentiment Distribution
          </h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#ffffff",
                    border: "1px solid #e5e7eb",
                    borderRadius: "8px",
                  }}
                  itemStyle={{ color: "#000000" }}
                  labelStyle={{ color: "#000000" }}
                />
                <Legend
                  formatter={(value) => (
                    <span className="text-black">{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Sentiment Cards */}
        <div className="space-y-4">
          {(["positif", "negatif", "netral"] as const).map((sentiment) => {
            const Icon = ICONS[sentiment];
            const color = COLORS[sentiment];
            const count = data.counts[sentiment];
            const percentage = ((count / total) * 100).toFixed(1);

            return (
              <div
                key={sentiment}
                className="bg-white rounded-xl border border-border p-6"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div
                      className="p-3 rounded-lg"
                      style={{ backgroundColor: `${color}20` }}
                    >
                      <Icon size={24} style={{ color }} />
                    </div>
                    <div>
                      <h4 className="font-semibold text-black">
                        {LABELS[sentiment]}
                      </h4>
                      <p className="text-sm text-black">
                        {count} mentions
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold" style={{ color }}>
                      {percentage}%
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Recent by Sentiment */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {(["positif", "negatif", "netral"] as const).map((sentiment) => {
          const mentions = data.breakdown[sentiment].slice(0, 5);
          const color = COLORS[sentiment];

          return (
            <div
              key={sentiment}
              className="bg-white rounded-xl border border-border p-6"
            >
              <h3
                className="text-lg font-semibold mb-4"
                style={{ color }}
              >
                {LABELS[sentiment]} Mentions
              </h3>
              <div className="space-y-3">
                {mentions.map((mention) => (
                  <div
                    key={mention.id}
                    className="border-l-2 pl-3 py-1"
                    style={{ borderColor: color }}
                  >
                    <p className="text-sm text-black line-clamp-2">
                      {mention.title}
                    </p>
                    <p className="text-xs text-black mt-1">
                      {mention.author} •{" "}
                      {new Date(mention.date).toLocaleDateString("id-ID", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}