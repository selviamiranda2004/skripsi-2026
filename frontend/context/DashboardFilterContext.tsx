"use client";

import { createContext, useContext, useMemo, useState, ReactNode } from "react";

/**
 * Filter range tanggal untuk dashboard admin.
 * Format tanggal: "YYYY-MM-DD" (cocok dengan input[type=date] dan SQL ::date).
 * null = tidak ada filter di sisi tersebut.
 *
 * RANGE VALID: Jan 1, 2026 - May 31, 2026 (sesuai window ingest skripsi).
 * Semua kalkulasi tanggal pakai timezone WIB (Asia/Jakarta).
 */

/** Range constant — match backend MENTION_DATE_MIN/MAX di main.py */
export const MENTION_DATE_MIN_STR = "2026-04-01";
export const MENTION_DATE_MAX_STR = "2026-05-31";

export interface DashboardFilterValue {
  startDate: string | null;
  endDate: string | null;
  setRange: (start: string | null, end: string | null) => void;
  /** Build query string buat dilampirin ke fetch URL: "?start_date=...&end_date=..." */
  queryString: string;
  /** Min/Max valid range, untuk attribute di <input type="date"> */
  minDate: string;
  maxDate: string;
}

const DashboardFilterContext = createContext<DashboardFilterValue | null>(null);

/**
 * Format Date jadi "YYYY-MM-DD" di timezone WIB (Asia/Jakarta).
 * Memastikan konsisten meskipun browser di timezone lain.
 */
function fmtWIB(d: Date): string {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Jakarta",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  return formatter.format(d);
}

/** Clamp tanggal "YYYY-MM-DD" ke [MIN, MAX] */
export function clampToValidRange(dateStr: string): string {
  if (dateStr < MENTION_DATE_MIN_STR) return MENTION_DATE_MIN_STR;
  if (dateStr > MENTION_DATE_MAX_STR) return MENTION_DATE_MAX_STR;
  return dateStr;
}

/** Hari ini WIB -> YYYY-MM-DD (clamped ke valid range) */
export function todayStr(): string {
  return clampToValidRange(fmtWIB(new Date()));
}

/**
 * Hari ini (versi clamped, hasil todayStr()) dikurangi N hari -> YYYY-MM-DD.
 * PENTING: hitung mundurnya dari todayStr() (yang sudah di-clamp), BUKAN dari
 * tanggal asli new Date(). Kalau dihitung dari tanggal asli, begitu tanggal
 * asli sudah lewat MAX, daysAgo(7) dan daysAgo(14) akan ikut ter-clamp ke MAX
 * yang sama dengan "hari ini" — membuat preset 7/14 hari terasa "tidak ngefek"
 * karena hasilnya sama persis dengan preset "Hari ini".
 */
export function daysAgo(days: number): string {
  const baseStr = todayStr(); // sudah ter-clamp ke [MIN, MAX]
  const [y, m, d] = baseStr.split("-").map(Number);
  // UTC date untuk hindari DST/timezone artifacts saat operasi tanggal
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() - days);
  const result = `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(
    2,
    "0"
  )}-${String(dt.getUTCDate()).padStart(2, "0")}`;
  return clampToValidRange(result);
}

export function DashboardFilterProvider({ children }: { children: ReactNode }) {
  // Default: 30 hari terakhir di WIB (clamped). User bisa tekan Reset
  // untuk lihat seluruh range Jan-Mei 2026.
  const [startDate, setStartDate] = useState<string | null>(daysAgo(30));
  const [endDate, setEndDate] = useState<string | null>(todayStr());

  const value = useMemo<DashboardFilterValue>(() => {
    const params = new URLSearchParams();
    if (startDate) params.set("start_date", startDate);
    if (endDate) params.set("end_date", endDate);
    const qs = params.toString();

    return {
      startDate,
      endDate,
      setRange: (start, end) => {
        setStartDate(start ? clampToValidRange(start) : null);
        setEndDate(end ? clampToValidRange(end) : null);
      },
      queryString: qs ? `?${qs}` : "",
      minDate: MENTION_DATE_MIN_STR,
      maxDate: MENTION_DATE_MAX_STR,
    };
  }, [startDate, endDate]);

  return (
    <DashboardFilterContext.Provider value={value}>
      {children}
    </DashboardFilterContext.Provider>
  );
}

/**
 * Hook untuk komponen dashboard yang butuh filter date.
 * Kalau dipakai di luar Provider, fallback ke filter kosong (no-op) supaya gak crash.
 */
export function useDashboardFilter(): DashboardFilterValue {
  const ctx = useContext(DashboardFilterContext);
  if (!ctx) {
    return {
      startDate: null,
      endDate: null,
      setRange: () => {},
      queryString: "",
      minDate: MENTION_DATE_MIN_STR,
      maxDate: MENTION_DATE_MAX_STR,
    };
  }
  return ctx;
}