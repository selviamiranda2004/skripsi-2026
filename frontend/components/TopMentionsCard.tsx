"use client";

import useSWR from "swr";
import { fetcher, BASE_URL } from "@/services/api";
import { useDashboardFilter } from "@/context/DashboardFilterContext";
import { Flame, ExternalLink, Calendar, Newspaper } from "lucide-react";

interface TopMention {
  title: string;
  url: string | null;
  author: string | null;
  date: string | null;
  sentiment: "positif" | "negatif" | "netral";
  outlet_count: number;
  mention_count: number;
  outlets: string[];
}

interface TopMentionsData {
  top_mentions: TopMention[];
}

const SENTIMENT_STYLE: Record<string, string> = {
  positif: "bg-green-500/10 text-green-500 border-green-500/30",
  negatif: "bg-red-500/10 text-red-500 border-red-500/30",
  netral: "bg-gray-500/10 text-gray-400 border-gray-500/30",
};

function formatDate(s: string | null): string {
  if (!s) return "-";
  try {
    const d = new Date(s);
    return d.toLocaleDateString("id-ID", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return s;
  }
}

function CardSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-border p-6">
      <div className="h-6 w-48 bg-gray-200 rounded mb-6 animate-pulse" />
      <div className="space-y-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="space-y-2">
            <div className="h-4 w-full bg-gray-200 rounded animate-pulse" />
            <div className="h-3 w-1/2 bg-gray-200 rounded animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TopMentionsCard() {
  const { queryString } = useDashboardFilter();
  const sep = queryString ? "&" : "?";
  const { data, error, isLoading } = useSWR<TopMentionsData>(
    `${BASE_URL}/top-mentions${queryString}${sep}limit=5`,
    fetcher
  );

  if (isLoading) return <CardSkeleton />;

  if (error || !data) {
    return (
      <div className="bg-white rounded-xl border border-border p-6">
        <h3 className="text-lg font-semibold text-black mb-2">
          Top 5 Berita Trending
        </h3>
        <p className="text-destructive text-sm">Gagal memuat data trending mentions.</p>
      </div>
    );
  }

  const items = data.top_mentions ?? [];

  return (
    <div className="bg-white rounded-xl border border-border p-6">
      <div className="flex items-center gap-2 mb-1">
        <Flame size={18} className="text-orange-500" />
        <h3 className="text-lg font-semibold text-black">
          Top 5 Berita Trending
        </h3>
      </div>
      <p className="text-xs text-black mb-5">
        Berita yang paling banyak dibahas (diukur dari jumlah pemberitaan untuk topik serupa).
      </p>

      {items.length === 0 ? (
        <p className="text-sm text-black py-8 text-center">
          Belum ada data dalam rentang tanggal ini.
        </p>
      ) : (
        <div className="space-y-3">
          {items.map((item, index) => (
            <div
              key={`${item.url || item.title}-${index}`}
              className="flex gap-3 p-3 rounded-lg border border-border/50 hover:border-border hover:bg-gray-50 transition group"
            >
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-bold">
                {index + 1}
              </div>

              <div className="flex-1 min-w-0">
                {item.url ? (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-black hover:text-primary transition flex items-start gap-1 group/link"
                  >
                    <span className="line-clamp-2">{item.title}</span>
                    <ExternalLink
                      size={12}
                      className="flex-shrink-0 mt-0.5 opacity-0 group-hover/link:opacity-100 transition"
                    />
                  </a>
                ) : (
                  <p className="text-sm font-medium text-black line-clamp-2">
                    {item.title}
                  </p>
                )}

                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2 text-xs text-black">
                  {item.author && (
                    <span className="font-medium">{item.author}</span>
                  )}
                  {item.date && (
                    <span className="flex items-center gap-1">
                      <Calendar size={11} />
                      {formatDate(item.date)}
                    </span>
                  )}
                  <span
                    className={`px-2 py-0.5 rounded-full border text-[11px] font-medium ${
                      SENTIMENT_STYLE[item.sentiment] || SENTIMENT_STYLE.netral
                    }`}
                  >
                    {item.sentiment}
                  </span>
                  <span
                    className="flex items-center gap-1 font-medium text-orange-500"
                    title={`${item.outlet_count} outlet meliput: ${item.outlets.join(", ")}`}
                  >
                    <Newspaper size={11} />
                    {item.mention_count} pemberitaan
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}