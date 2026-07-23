"use client";

import useSWR, { mutate } from "swr";
import { BASE_URL, fetcher } from "@/services/api";
import {
  ExternalLink,
  Calendar,
  User,
  ThumbsUp,
  ThumbsDown,
  HelpCircle,
  Trash2,
} from "lucide-react";

interface Mention {
  id: number;
  title: string;
  author: string;
  date: string;
  sentiment: "positif" | "negatif" | "netral";
  source: string;
}

interface MentionsData {
  mentions: Mention[];
}

export default function AdminMentionsPage() {
  const mentionsKey = `${BASE_URL}/mentions`;

  const { data, error, isLoading } = useSWR<MentionsData>(
    mentionsKey,
    fetcher
  );

  const updateSentiment = async (
    id: number,
    sentiment: "positif" | "negatif" | "netral"
  ) => {
    try {
      await fetch(`${BASE_URL}/mentions/${id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ sentiment }),
      });

      mutate(mentionsKey);
    } catch (err) {
      console.error("Failed to update sentiment:", err);
    }
  };

  const deleteMention = async (id: number) => {
    try {
      await fetch(`${BASE_URL}/mentions/${id}`, {
        method: "DELETE",
      });

      mutate(mentionsKey);
    } catch (err) {
      console.error("Failed to delete mention:", err);
    }
  };

  if (isLoading) return <div className="p-6">Loading...</div>;

  if (error) return <div className="p-6 text-red-500">{error.message}</div>;

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-6">Admin - Mentions</h2>

      <div className="space-y-6">
        {data?.mentions?.map((mention) => (
          <div
            key={mention.id}
            className="border rounded-lg p-4 hover:border-blue-400 transition"
          >
            {/* INFO */}
            <div className="flex justify-between gap-4">
              <div className="flex-1">
                <h3 className="font-medium mb-2">{mention.title}</h3>

                <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                  <span className="flex items-center gap-1">
                    <User size={14} />
                    {mention.author}
                  </span>

                  <span className="flex items-center gap-1">
                    <Calendar size={14} />
                    {mention.date
                      ? new Date(mention.date).toLocaleDateString("id-ID")
                      : "-"}
                  </span>

                  <span className="flex items-center gap-1">
                    <ExternalLink size={14} />
                    {mention.source}
                  </span>
                </div>
              </div>

              {/* DELETE */}
              <button
                onClick={() => deleteMention(mention.id)}
                className="text-red-500 hover:text-red-700"
              >
                <Trash2 size={18} />
              </button>
            </div>

            {/* SENTIMENT CONTROL */}
            <div className="flex gap-2 mt-4">
              <button
                onClick={() => updateSentiment(mention.id, "positif")}
                className={`w-10 h-10 rounded-full flex items-center justify-center border ${mention.sentiment === "positif"
                    ? "bg-green-500 text-white"
                    : "hover:bg-green-200"
                  }`}
              >
                <ThumbsUp size={18} />
              </button>

              <button
                onClick={() => updateSentiment(mention.id, "negatif")}
                className={`w-10 h-10 rounded-full flex items-center justify-center border ${mention.sentiment === "negatif"
                    ? "bg-red-500 text-white"
                    : "hover:bg-red-200"
                  }`}
              >
                <ThumbsDown size={18} />
              </button>

              <button
                onClick={() => updateSentiment(mention.id, "netral")}
                className={`w-10 h-10 rounded-full flex items-center justify-center border ${mention.sentiment === "netral"
                    ? "bg-yellow-400 text-white"
                    : "hover:bg-yellow-200"
                  }`}
              >
                <HelpCircle size={18} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}