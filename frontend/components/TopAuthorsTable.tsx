"use client";

import useSWR from "swr";
import { fetcher, BASE_URL } from "@/services/api";
import { useDashboardFilter } from "@/context/DashboardFilterContext";

interface TopAuthor {
  author: string;
  count: number;
}

interface TopAuthorsData {
  top_authors: TopAuthor[];
}

function TableSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-border p-6">
      <div className="h-6 w-32 bg-gray-200 rounded mb-6 animate-pulse" />
      <div className="space-y-3">
        {[...Array(10)].map((_, i) => (
          <div key={i} className="flex justify-between items-center">
            <div className="h-4 w-32 bg-gray-200 rounded animate-pulse" />
            <div className="h-4 w-12 bg-gray-200 rounded animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TopAuthorsTable() {
  const { queryString } = useDashboardFilter();
  const { data, error, isLoading } = useSWR<TopAuthorsData>(
    `${BASE_URL}/top-authors${queryString}`,
    fetcher
  );

  if (isLoading) {
    return <TableSkeleton />;
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-xl border border-border p-6">
        <p className="text-destructive">Error loading top authors data</p>
      </div>
    );
  }

  const maxCount = Math.max(...data.top_authors.map((a) => a.count));

  return (
    <div className="bg-white rounded-xl border border-border p-6">
      <h3 className="text-lg font-semibold text-black mb-6">
        Top 10 Authors
      </h3>
      <div className="space-y-3">
        {data.top_authors.map((author, index) => (
          <div key={author.author} className="flex items-center gap-4">
            <span className="text-black text-sm w-6">
              {index + 1}.
            </span>
            <div className="flex-1">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-black">
                  {author.author}
                </span>
                <span className="text-sm text-black">
                  {author.count} mentions
                </span>
              </div>
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all duration-500"
                  style={{ width: `${(author.count / maxCount) * 100}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}