"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import { fetcher, BASE_URL } from "@/services/api";
import type { MentionsData } from "@/services/api";
import {
  ThumbsUp,
  ThumbsDown,
  HelpCircle,
  Trash2,
  Loader2,
  AlertCircle,
  SearchX,
  ExternalLink,
} from "lucide-react";
import DateRangePicker from "./DateRangePicker";
import {
  DashboardFilterProvider,
  useDashboardFilter,
} from "@/context/DashboardFilterContext";

type Sentiment = "positif" | "negatif" | "netral";

const getToken = () =>
  typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;

type SentimentConfigItem = {
  label: string;
  icon: React.ReactNode;
  activeClass: string;
  hoverClass: string;
};

const sentimentConfig: { [K in Sentiment]: SentimentConfigItem } = {
  positif: {
    label: "Positif",
    icon: <ThumbsUp size={16} />,
    activeClass: "bg-green-500 border-green-500 text-white",
    hoverClass: "hover:bg-green-100 hover:border-green-400 hover:text-green-600",
  },
  negatif: {
    label: "Negatif",
    icon: <ThumbsDown size={16} />,
    activeClass: "bg-red-500 border-red-500 text-white",
    hoverClass: "hover:bg-red-100 hover:border-red-400 hover:text-red-600",
  },
  netral: {
    label: "Netral",
    icon: <HelpCircle size={16} />,
    activeClass: "bg-yellow-400 border-yellow-400 text-white",
    hoverClass: "hover:bg-yellow-100 hover:border-yellow-400 hover:text-yellow-600",
  },
};

const SentimentBadge = ({ sentiment }: { sentiment: Sentiment | null }) => {
  if (!sentiment)
    return (
      <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-400 border border-gray-200">
        Belum ditandai
      </span>
    );
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded-full font-medium inline-flex items-center gap-1 ${
        sentiment === "positif"
          ? "bg-green-100 text-green-700 border border-green-300"
          : sentiment === "negatif"
          ? "bg-red-100 text-red-700 border border-red-300"
          : "bg-yellow-100 text-yellow-700 border border-yellow-300"
      }`}
    >
      {sentimentConfig[sentiment].icon}
      {sentimentConfig[sentiment].label}
    </span>
  );
};

export default function AdminMentionsPage() {
  return (
    <DashboardFilterProvider>
      <AdminMentionsContent />
    </DashboardFilterProvider>
  );
}

function AdminMentionsContent() {
  // Filter tanggal dipakai server-side: backend filter pakai mention_date
  // (publish date berita), jadi yang muncul HANYA berita publish di range itu.
  const { queryString } = useDashboardFilter();
  const mentionsUrl = `${BASE_URL}/mentions${queryString}`;

  const { data, error: fetchError, isLoading } = useSWR<MentionsData>(
    mentionsUrl,
    fetcher
  );

  const mentions = data?.mentions || [];

  const [search, setSearch] = useState("");
  const [filterSentiment, setFilterSentiment] = useState<Sentiment | "semua">(
    "semua"
  );
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // Server-side filter sudah handle date. Tinggal filter search + sentiment di client.
  const searchFiltered = mentions.filter((m) => {
    const keyword = search.toLowerCase();
    return (
      m.title.toLowerCase().includes(keyword) ||
      m.author.toLowerCase().includes(keyword)
    );
  });

  const filteredMentions = searchFiltered.filter((m) => {
    return filterSentiment === "semua" || m.sentiment === filterSentiment;
  });

  const countBySentiment = (s: Sentiment) =>
    searchFiltered.filter((m) => m.sentiment === s).length;

  const updateSentiment = async (id: number, sentiment: Sentiment) => {
    if (updatingId === id) return;
    setUpdatingId(id);

    mutate(
      mentionsUrl,
      (prev: MentionsData | undefined) => ({
        ...prev,
        mentions:
          prev?.mentions.map((m) =>
            m.id === id ? { ...m, sentiment } : m
          ) ?? [],
      }),
      false
    );

    try {
      const token = getToken();
      const res = await fetch(`${BASE_URL}/mentions/${id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ sentiment }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.detail || `HTTP ${res.status}`);
      }

      showToast(`Sentiment diubah ke "${sentiment}"`, "success");
      mutate(mentionsUrl);
    } catch (err: any) {
      console.error("Update sentiment failed:", err);
      showToast(`Gagal: ${err.message}`, "error");
      mutate(mentionsUrl);
    } finally {
      setUpdatingId(null);
    }
  };

  const deleteMention = async (id: number, title: string) => {
    if (!confirm(`Hapus mention "${title}"?\nAksi ini tidak bisa dibatalkan.`)) return;

    setDeletingId(id);

    mutate(
      mentionsUrl,
      (prev: MentionsData | undefined) => ({
        ...prev,
        mentions: prev?.mentions.filter((m) => m.id !== id) ?? [],
      }),
      false
    );

    try {
      const token = getToken();
      const res = await fetch(`${BASE_URL}/mentions/${id}`, {
        method: "DELETE",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.detail || `HTTP ${res.status}`);
      }

      showToast("Mention berhasil dihapus", "success");
      mutate(mentionsUrl);
    } catch (err: any) {
      console.error("Delete mention failed:", err);
      showToast(`Gagal: ${err.message}`, "error");
      mutate(mentionsUrl);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="relative">

      {/* TOAST */}
      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow text-white text-sm font-medium flex items-center gap-2 ${
            toast.type === "success" ? "bg-green-500" : "bg-red-500"
          }`}
        >
          {toast.type === "error" && <AlertCircle size={16} />}
          {toast.message}
        </div>
      )}

      {/* HEADER */}
      <div className="flex flex-col sm:flex-row justify-between gap-4 mb-4">
        <div>
           <h2 className="text-xl font-bold text-black">📢 Mentions Admin</h2>
           <p className="text-sm text-black mt-0.5">Total: {mentions.length} mention</p>
        </div>
        <input
          type="text"
          placeholder="Cari judul atau author..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border px-4 py-2.5 rounded-lg w-full sm:w-72 text-sm bg-white text-black focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
      </div>

      {/* DATE RANGE FILTER — pakai DateRangePicker shared (preset Hari ini, 7 hari, dll, constraint Jan-Mei 2026) */}
      <div className="mb-4">
        <DateRangePicker />
      </div>

      {/* FILTER CHIPS */}
      <div className="flex flex-wrap gap-2 mb-5">
        {(["semua", "positif", "negatif", "netral"] as const).map((s) => {
  const count = s === "semua"
    ? searchFiltered.length
    : countBySentiment(s as Sentiment);

  const activeColorClass =
    s === "positif"
      ? "bg-green-500 text-white border-green-500"
      : s === "negatif"
      ? "bg-red-500 text-white border-red-500"
      : s === "netral"
      ? "bg-yellow-400 text-white border-yellow-400"
      : "bg-slate-800 text-white border-slate-800"; // "semua"

  return (
              <button
      key={s}
      onClick={() => setFilterSentiment(s)}
      className={`px-3 py-1.5 rounded-full text-xs font-medium border transition ${
        filterSentiment === s
          ? activeColorClass
          : "bg-white text-black border-gray-200 hover:border-slate-400"
      }`}
    >
      {s.charAt(0).toUpperCase() + s.slice(1)} ({count})
    </button>
          );
        })}
      </div>

      {/* LOADING */}
      {isLoading && (
                <div className="flex items-center justify-center py-16 gap-2 text-black">
          <Loader2 size={20} className="animate-spin" />
          <span className="text-sm">Memuat mentions...</span>
        </div>
      )}

      {/* ERROR */}
      {fetchError && !isLoading && (
        <div className="flex flex-col items-center justify-center py-16 gap-2 text-red-400">
          <AlertCircle size={32} />
          <p className="text-sm font-medium">Gagal memuat data mentions</p>
             <p className="text-xs text-black">{fetchError.message}</p>
          <button onClick={() => mutate(mentionsUrl)} className="text-xs text-blue-500 underline">
            Coba lagi
          </button>
        </div>
      )}

      {/* EMPTY */}
      {!isLoading && !fetchError && filteredMentions.length === 0 && (
               <div className="flex flex-col items-center justify-center py-16 gap-2 text-black">
          <SearchX size={32} />
          <p className="text-sm">
            {search || filterSentiment !== "semua" || queryString
              ? "Tidak ada hasil yang cocok untuk filter ini"
              : "Belum ada mention"}
          </p>
        </div>
      )}

      {/* LIST */}
      <div className="space-y-3">
        {filteredMentions.map((m) => {
          const isUpdating = updatingId === m.id;
          const isDeleting = deletingId === m.id;

          return (
            <div
              key={m.id}
           className={`border rounded-xl p-4 transition-all bg-white text-black ${
                isDeleting ? "opacity-40 pointer-events-none" : ""
              }`}
            >
              <div className="flex items-start justify-between gap-2 mb-1">
                {/* TITLE — klik buka URL berita */}
                      <p className="font-semibold text-sm leading-snug text-black">
                  📰{" "}
                  {m.url ? (
                    <a
                      href={m.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-blue-400 hover:underline transition"
                    >
                      {m.title}
                    </a>
                  ) : (
                    m.title
                  )}
                </p>
                <SentimentBadge sentiment={m.sentiment ?? null} />
              </div>

              {/* AUTHOR + LINK ARTIKEL */}
             <div className="flex items-center gap-3 text-xs text-black mb-3">
                <span>👤 {m.author}</span>
                {m.url && (
                  <a
                    href={m.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 hover:text-blue-400 transition"
                  >
                    <ExternalLink size={12} />
                    Buka artikel
                  </a>
                )}
              </div>

              <div className="flex items-center gap-2">
                {(["positif", "negatif", "netral"] as Sentiment[]).map((s) => {
                  const cfg = sentimentConfig[s];
                  const isActive = m.sentiment === s;
                  return (
                    <button
                      key={s}
                      onClick={() => updateSentiment(m.id, s)}
                      disabled={isUpdating}
                      title={cfg.label}
                      className={`w-9 h-9 rounded-full flex items-center justify-center border text-sm transition-all ${
                        isActive
                          ? cfg.activeClass
                          : `bg-white border-gray-200 text-black ${cfg.hoverClass}`
                      } ${isUpdating ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                    >
                      {isUpdating && isActive ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        cfg.icon
                      )}
                    </button>
                  );
                })}

                <button
                  onClick={() => deleteMention(m.id, m.title)}
                  disabled={isDeleting}
                  title="Hapus mention"
                 className={`w-9 h-9 rounded-full flex items-center justify-center border ml-auto transition-all
                    bg-white border-gray-200 text-black
                    hover:bg-red-100 hover:border-red-400 hover:text-red-500
                    ${isDeleting ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                >
                  {isDeleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={15} />}
                </button>
              </div>

              <p className="text-xs text-black mt-3">
                📅{" "}
                {m.date
                  ? new Date(m.date).toLocaleDateString("id-ID", {
                      day: "2-digit",
                      month: "long",
                      year: "numeric",
                    })
                  : "Tanggal tidak tersedia"}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
