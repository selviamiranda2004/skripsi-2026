"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { mutate } from "swr";
import { BASE_URL } from "@/services/api";

/**
 * Endpoint backend yang isinya bergantung pada data mentions.
 * Setelah refresh news selesai, semua SWR cache yang URL-nya mulai dengan
 * salah satu dari prefix di bawah akan di-revalidate (termasuk variasi
 * dengan query string ?start_date=... dari date filter di dashboard).
 */
const REVALIDATE_PREFIXES = [
  `${BASE_URL}/mentions`,
  `${BASE_URL}/sentiment-breakdown`,
  `${BASE_URL}/summary`,
  `${BASE_URL}/timeline`,
  `${BASE_URL}/top-authors`,
  `${BASE_URL}/top-mentions`,
  `${BASE_URL}/wordcloud`,
];

/** Filter function buat SWR mutate: match semua key yang mulai dengan prefix di atas */
const shouldRevalidate = (key: unknown): boolean =>
  typeof key === "string" && REVALIDATE_PREFIXES.some((p) => key.startsWith(p));

export interface AutoRefreshState {
  isRefreshing: boolean;
  lastRefreshAt: Date | null;
  secondsUntilNext: number;
  error: string | null;
  /** Warning non-fatal (e.g. RSS kosong karena DNS issue) — refresh tetap "sukses" dari sisi HTTP */
  warning: string | null;
  lastTotal: number | null;
  refreshNow: () => Promise<void>;
  enabled: boolean;
  setEnabled: (v: boolean) => void;
  intervalSec: number;
}

interface Options {
  /** interval auto-refresh dalam detik (default 30) */
  intervalSec?: number;
  /** apakah auto-refresh aktif (default true) */
  initialEnabled?: boolean;
}

/**
 * Hook auto-refresh mentions:
 *  - Memanggil GET /refresh-news-test setiap `intervalSec` detik
 *  - Setelah sukses, revalidate semua SWR cache yang relevan
 *  - Mengembalikan state untuk ditampilkan di indikator UI
 */
export function useAutoRefreshNews({
  intervalSec = 30,
  initialEnabled = true,
}: Options = {}): AutoRefreshState {
  const [enabled, setEnabled] = useState(initialEnabled);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshAt, setLastRefreshAt] = useState<Date | null>(null);
  const [secondsUntilNext, setSecondsUntilNext] = useState(intervalSec);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [lastTotal, setLastTotal] = useState<number | null>(null);

  // pakai ref biar nggak ke-recreate setiap render
  const isRefreshingRef = useRef(false);

  const refreshNow = useCallback(async () => {
    if (isRefreshingRef.current) return;
    isRefreshingRef.current = true;
    setIsRefreshing(true);
    setError(null);
    setWarning(null);

    // Hard timeout 180 detik supaya indicator nggak nge-stuck kalau backend hang.
    // Dengan optimisasi bulk duplicate-check, refresh normal selesai < 20 detik,
    // tapi kita kasih buffer besar untuk koneksi lambat / Supabase pooler slow.
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 180_000);

    try {
      const res = await fetch(`${BASE_URL}/refresh-news-test`, {
        method: "GET",
        cache: "no-store",
        signal: controller.signal,
      });

      if (!res.ok) {
        // Coba ambil detail error dari body kalau ada
        const errBody = await res.json().catch(() => null);
        const detail = errBody?.detail || errBody?.message || "";
        throw new Error(
          detail ? `HTTP ${res.status}: ${detail}` : `HTTP ${res.status}`
        );
      }

      const data = await res.json().catch(() => ({}));
      const totalNum = typeof data?.total === "number" ? data.total : 0;
      setLastTotal(totalNum);
      setLastRefreshAt(new Date());

      // Surface warning dari backend (e.g. RSS kosong karena DNS issue ke Google News).
      // Backend balas 200 OK tapi pesan warning ada di body.
      if (typeof data?.warning === "string" && data.warning) {
        setWarning(data.warning);
      } else if (totalNum === 0 && data?.detail && Object.keys(data.detail).length === 0) {
        // Heuristik: total=0 + detail kosong = kemungkinan semua keyword fail fetch
        setWarning(
          "Tidak ada mention baru. Cek koneksi internet atau Google News mungkin sedang blok request."
        );
      }

      // Revalidate semua SWR cache yang relevan (termasuk URL dengan query string
      // dari date filter dashboard) supaya UI langsung update.
      await mutate(shouldRevalidate);
    } catch (err: any) {
      // Beda-beda kategori error biar gampang debug
      let msg: string;
      if (err?.name === "AbortError") {
        msg = "Timeout (>180s). Backend lambat atau Google News blok request.";
      } else if (err instanceof TypeError) {
        msg = "Backend tidak bisa dihubungi. Cek apakah uvicorn jalan.";
      } else {
        msg = err?.message || "Refresh gagal";
      }
      setError(msg);
    } finally {
      clearTimeout(timeoutId);
      isRefreshingRef.current = false;
      setIsRefreshing(false);
      setSecondsUntilNext(intervalSec);
    }
  }, [intervalSec]);

  // Tick countdown tiap 1 detik. Ketika countdown menyentuh 0, panggil refresh.
  useEffect(() => {
    if (!enabled) return;

    const tick = setInterval(() => {
      setSecondsUntilNext((prev) => {
        if (isRefreshingRef.current) return prev;
        if (prev <= 1) {
          // trigger refresh, lalu reset ke intervalSec di blok finally refreshNow
          refreshNow();
          return intervalSec;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(tick);
  }, [enabled, intervalSec, refreshNow]);

  // Reset countdown kalau interval berubah
  useEffect(() => {
    setSecondsUntilNext(intervalSec);
  }, [intervalSec]);

  return {
    isRefreshing,
    lastRefreshAt,
    secondsUntilNext,
    error,
    warning,
    lastTotal,
    refreshNow,
    enabled,
    setEnabled,
    intervalSec,
  };
}
