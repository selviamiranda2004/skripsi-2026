"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetcher, BASE_URL } from "@/services/api";
import {
  ExternalLink,
  Calendar,
  User,
  ThumbsUp,
  ThumbsDown,
  HelpCircle,
} from "lucide-react";
import DateRangePicker from "./DateRangePicker";
import {
  DashboardFilterProvider,
  useDashboardFilter,
} from "@/context/DashboardFilterContext";

interface Mention {
  id: number;
  title: string;
  author: string;
  date: string;
  sentiment: "positif" | "negatif" | "netral";
  source: string;
  url: string;
}

interface MentionsData {
  mentions: Mention[];
}

function TableSkeleton() {
  return (
    <div className="space-y-4">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="border p-4 rounded animate-pulse bg-gray-900">
          <div className="h-5 w-2/3 bg-gray-300 mb-3 rounded" />
          <div className="h-4 w-1/3 bg-gray-300 rounded" />
        </div>
      ))}
    </div>
  );
}

type SentimentFilter = "all" | "positif" | "negatif" | "netral";

export default function MentionsPage() {
  return (
    <DashboardFilterProvider>
      <MentionsContent />
    </DashboardFilterProvider>
  );
}

function MentionsContent() {
  // Filter tanggal dipakai server-side: backend filter pakai mention_date
  // (publish date berita), jadi yang muncul HANYA berita publish di range itu.
  const { queryString } = useDashboardFilter();
  const mentionsUrl = `${BASE_URL}/mentions${queryString}`;

  const { data, error, isLoading } = useSWR<MentionsData>(
    mentionsUrl,
    fetcher
  );

  const [search, setSearch] = useState("");
  const [sentimentFilter, setSentimentFilter] = useState<SentimentFilter>("all");

  if (isLoading) {
    return (
      <div>
        <h2 className="text-2xl font-bold mb-6 text-black">All Mentions</h2>
        <div className="mb-4">
          <DateRangePicker />
        </div>
        <TableSkeleton />
      </div>
    );
  }

  if (error) {
    return <div className="text-destructive">{error.message}</div>;
  }

  // Server-side filter sudah handle date. Tinggal filter search + sentiment di client.
  const searchFiltered = data?.mentions?.filter((mention) => {
    const keyword = search.toLowerCase();
    return (
      mention.title.toLowerCase().includes(keyword) ||
      mention.author.toLowerCase().includes(keyword) ||
      mention.source.toLowerCase().includes(keyword)
    );
  }) ?? [];

  const sentimentCount = {
    positif: searchFiltered.filter((m) => m.sentiment === "positif").length,
    negatif: searchFiltered.filter((m) => m.sentiment === "negatif").length,
    netral: searchFiltered.filter((m) => m.sentiment === "netral").length,
  };

  const filteredMentions = sentimentFilter === "all"
    ? searchFiltered
    : searchFiltered.filter((m) => m.sentiment === sentimentFilter);

  const handleSentimentClick = (s: SentimentFilter) => {
    setSentimentFilter((prev) => (prev === s ? "all" : s));
  };

  return (
    <div>
      {/* HEADER + SEARCH */}
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-2xl font-bold text-black">All Mentions</h2>
        <input
          type="text"
          placeholder="Search mentions..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border px-4 py-3 rounded-lg w-80 text-base focus:outline-none focus:ring-2 focus:ring-blue-400"
          style={{ color: "black" }}
        />
      </div>

      {/* DATE RANGE FILTER — pakai DateRangePicker shared (preset Hari ini, 7/14/30 hari, Reset ke Jan-Mei 2026) */}
      <div className="mb-4">
        <DateRangePicker />
      </div>

      {/* FILTER BADGES */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <button
          onClick={() => setSentimentFilter("all")}
          className={`flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium border transition ${
            sentimentFilter === "all"
              ? "bg-slate-800 text-white border-slate-800"
              : "bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-200"
          }`}
        >
          Semua: {searchFiltered.length}
        </button>

        <button
          onClick={() => handleSentimentClick("positif")}
          className={`flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium border transition ${
            sentimentFilter === "positif"
              ? "bg-green-500 text-white border-green-500"
              : "bg-green-100 text-green-700 border-green-200 hover:bg-green-200"
          }`}
        >
          <ThumbsUp size={13} />
          Positif: {sentimentCount.positif}
        </button>

        <button
          onClick={() => handleSentimentClick("negatif")}
          className={`flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium border transition ${
            sentimentFilter === "negatif"
              ? "bg-red-500 text-white border-red-500"
              : "bg-red-100 text-red-700 border-red-200 hover:bg-red-200"
          }`}
        >
          <ThumbsDown size={13} />
          Negatif: {sentimentCount.negatif}
        </button>

        <button
          onClick={() => handleSentimentClick("netral")}
          className={`flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium border transition ${
            sentimentFilter === "netral"
              ? "bg-yellow-500 text-white border-yellow-500"
              : "bg-yellow-100 text-yellow-700 border-yellow-200 hover:bg-yellow-200"
          }`}
        >
          <HelpCircle size={13} />
          Netral: {sentimentCount.netral}
        </button>
      </div>

      {/* LIST */}
      <div className="space-y-4">
        {filteredMentions.length === 0 ? (
            <p className="text-black text-sm text-center py-8">
            Tidak ada mention ditemukan
          </p>
        ) : (
          filteredMentions.map((mention) => (
            <div
              key={mention.id}
              className="bg-white border border-gray-200 rounded-xl p-4 hover:border-gray-400 transition"
            >
              <div className="flex-1">
                {/* TITLE — klik buka URL berita */}
                <h3 className="font-medium mb-2">
                  {mention.url ? (
                    <a
                      href={mention.url}
                      target="_blank"
                      rel="noopener noreferrer"
                       className="text-black hover:text-blue-500 hover:underline transition"
                    >
                      {mention.title}
                    </a>
                  ) : (
                    <span className="text-white">{mention.title}</span>
                  )}
                </h3>

                <div className="flex flex-wrap gap-4 text-sm text-black">
                  <span className="flex items-center gap-1">
                    <User size={14} />
                    {mention.author}
                  </span>
                  <span className="flex items-center gap-1">
                    <Calendar size={14} />
                    {mention.date
                      ? new Date(mention.date).toLocaleDateString("id-ID", {
                          day: "numeric",
                          month: "long",
                          year: "numeric",
                        })
                      : "-"}
                  </span>
                  {mention.url ? (
                    <a
                      href={mention.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 hover:text-blue-500 transition"
                    >
                      <ExternalLink size={14} />
                      {mention.source}
                    </a>
                  ) : (
                    <span className="flex items-center gap-1">
                      <ExternalLink size={14} />
                      {mention.source}
                    </span>
                  )}
                </div>
              </div>

              {/* SENTIMENT INDICATOR */}
              <div className="flex gap-2 mt-4">
                <button
                  className={`w-10 h-10 rounded-full flex items-center justify-center border transition ${
                    mention.sentiment === "positif"
                      ? "bg-green-500 border-green-500 text-white"
                      : "border-gray-300 text-gray-400 hover:bg-green-500/20 hover:border-green-500 hover:text-green-400"
                  }`}
                >
                  <ThumbsUp size={16} />
                </button>
                <button
                  className={`w-10 h-10 rounded-full flex items-center justify-center border transition ${
                    mention.sentiment === "negatif"
                      ? "bg-red-500 border-red-500 text-white"
                      : "border-gray-300 text-gray-400 hover:bg-red-500/20 hover:border-red-500 hover:text-red-400"
                  }`}
                >
                  <ThumbsDown size={16} />
                </button>
                <button
                  className={`w-10 h-10 rounded-full flex items-center justify-center border transition ${
                    mention.sentiment === "netral"
                      ? "bg-yellow-400 border-yellow-400 text-white"
                      : "border-gray-300 text-gray-400 hover:bg-yellow-400/20 hover:border-yellow-400 hover:text-yellow-400"
                  }`}
                >
                  <HelpCircle size={16} />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
