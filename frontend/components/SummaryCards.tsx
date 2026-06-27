"use client";

import useSWR from "swr";
import { fetcher, BASE_URL } from "@/services/api";
import { useDashboardFilter } from "@/context/DashboardFilterContext";
import {
  Newspaper,
  Users,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";

interface SummaryData {
  total_mentions: number;
  unique_authors: number;
  total_users?: number;
  sentiment: {
    positif: number;
    negatif: number;
    netral: number;
  };
}

function CardSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-border p-6 animate-pulse">
      <div className="h-4 w-24 bg-gray-200 rounded mb-4" />
      <div className="h-8 w-16 bg-gray-200 rounded" />
    </div>
  );
}

export default function SummaryCards({
  role = "user",
}: {
  role?: "admin" | "user";
}) {
  const { queryString } = useDashboardFilter();
  const { data, error, isLoading } = useSWR<SummaryData>(
    `${BASE_URL}/summary${queryString}`,
    fetcher
  );

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {[...Array(5)].map((_, i) => (
          <CardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-destructive/10 text-destructive rounded-xl p-4">
        Error loading summary data
      </div>
    );
  }

  const baseCards = [
    {
      title: "Total Mentions",
      value: data.total_mentions,
      icon: Newspaper,
      color: "text-primary",
      bgColor: "bg-primary/10",
    },
    {
      title: "Unique Authors",
      value: data.unique_authors,
      icon: Users,
      color: "text-chart-5",
      bgColor: "bg-chart-5/10",
    },
    {
      title: "Positive",
      value: data?.sentiment?.positif ?? 0,
      icon: TrendingUp,
      color: "text-positive",
      bgColor: "bg-positive/10",
    },
    {
      title: "Negative",
      value: data?.sentiment?.negatif ?? 0,
      icon: TrendingDown,
      color: "text-destructive",
      bgColor: "bg-destructive/10",
    },
    {
      title: "Neutral",
      value: data?.sentiment?.netral ?? 0,
      icon: Minus,
      color: "text-neutral-sentiment",
      bgColor: "bg-neutral-sentiment/10",
    },
  ];

  const adminCard =
    role === "admin"
      ? [
          {
            title: "Total Users",
            value: data.total_users || 0,
            icon: Users,
            color: "text-blue-500",
            bgColor: "bg-blue-500/10",
          },
        ]
      : [];

  const cards = [...adminCard, ...baseCards];

  return (
    <div
      className={`grid grid-cols-1 sm:grid-cols-2 ${
        role === "admin" ? "lg:grid-cols-6" : "lg:grid-cols-5"
      } gap-4`}
    >
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.title}
            className="bg-white rounded-xl border border-border p-6 hover:border-primary/50 transition-colors"
          >
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm text-black">
                {card.title}
              </span>
              <div className={`p-2 rounded-lg ${card.bgColor}`}>
                <Icon size={18} className={card.color} />
              </div>
            </div>
            <p className={`text-3xl font-bold ${card.color}`}>
              {card.value}
            </p>
          </div>
        );
      })}
    </div>
  );
}