export const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api";

export interface SummaryData {
  total_mentions: number;
  unique_authors: number;
  sentiment: {
    positif: number;
    negatif: number;
    netral: number;
  };
}

export interface TimelineItem {
  date: string;
  count: number;
}

export interface TimelineData {
  timeline: TimelineItem[];
}

export interface TopAuthor {
  author: string;
  count: number;
}

export interface TopAuthorsData {
  top_authors: TopAuthor[];
}

export interface WordCloudItem {
  text: string;
  value: number;
}

export interface WordCloudData {
  wordcloud: WordCloudItem[];
}

export interface Mention {
  id: number;
  title: string;
  author: string;
  date: string;
  sentiment: "positif" | "negatif" | "netral";
  source: string;
    url?: string; // ✅ tambahan
}

export interface MentionsData {
  mentions: Mention[];
}

export interface SentimentBreakdownData {
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

// ========================
// CORE FETCH HELPER
// ========================
async function fetchData<T>(endpoint: string, token?: string): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, { headers });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }

  return response.json();
}

// ========================
// API METHODS
// ========================
export const api = {
  getSummary: (token?: string) => fetchData<SummaryData>("/summary", token),
  getTimeline: (token?: string) => fetchData<TimelineData>("/timeline", token),
  getTopAuthors: (token?: string) => fetchData<TopAuthorsData>("/top-authors", token),
  getWordCloud: (token?: string) => fetchData<WordCloudData>("/wordcloud", token),
  getMentions: (token?: string) => fetchData<MentionsData>("/mentions", token),
  getSentimentBreakdown: (token?: string) =>
    fetchData<SentimentBreakdownData>("/sentiment-breakdown", token),
};

// ========================
// SWR FETCHER (FIXED)
// ========================
export const fetcher = async (url: string) => {
  const token = localStorage.getItem("auth_token");

  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || "API Error");
  }

  return data;
};