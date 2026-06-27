"use client";

import useSWR from "swr";
import { fetcher, BASE_URL } from "@/services/api";
import { useDashboardFilter } from "@/context/DashboardFilterContext";
import { useMemo } from "react";

interface WordCloudItem {
  text: string;
  value: number;
}

interface WordCloudData {
  wordcloud: WordCloudItem[];
}

function WordCloudSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-border p-6">
      <div className="h-6 w-32 bg-gray-200 rounded mb-6 animate-pulse" />
      <div className="h-64 bg-gray-200 rounded animate-pulse flex items-center justify-center">
        <span className="text-black">Loading word cloud...</span>
      </div>
    </div>
  );
}

const colors = [
  "#3b82f6",
  "#22c55e",
  "#f59e0b",
  "#8b5cf6",
  "#ec4899",
  "#06b6d4",
  "#f97316",
];

export default function WordCloudChart() {
  const { queryString } = useDashboardFilter();
  const { data, error, isLoading } = useSWR<WordCloudData>(
    `${BASE_URL}/wordcloud${queryString}`,
    fetcher
  );

  const wordElements = useMemo(() => {
    const words = data?.wordcloud ?? [];

    if (words.length === 0) return null;

    const maxValue = Math.max(...words.map((w) => w.value));
    const minValue = Math.min(...words.map((w) => w.value));

    return words.map((word, index) => {
      const normalizedValue =
        (word.value - minValue) / (maxValue - minValue || 1);

      const fontSize = 12 + normalizedValue * 24;
      const color = colors[index % colors.length];

      return (
        <span
          key={word.text}
          className="inline-block px-2 py-1 hover:opacity-80 transition-opacity cursor-default"
          style={{
            fontSize: `${fontSize}px`,
            color,
            fontWeight: normalizedValue > 0.5 ? 600 : 400,
          }}
          title={`${word.text}: ${word.value} mentions`}
        >
          {word.text}
        </span>
      );
    });
  }, [data]);

  if (isLoading) {
    return <WordCloudSkeleton />;
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-xl border border-border p-6">
        <p className="text-destructive">Error loading wordcloud data</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-border p-6">
      <h3 className="text-lg font-semibold text-black mb-6">
        Word Cloud
      </h3>
      <div className="min-h-64 flex flex-wrap items-center justify-center gap-1 text-center leading-relaxed">
        {wordElements}
      </div>
    </div>
  );
}