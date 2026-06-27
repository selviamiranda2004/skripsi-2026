"use client";

import { Calendar, RotateCcw } from "lucide-react";
import {
  useDashboardFilter,
  todayStr,
  daysAgo,
} from "@/context/DashboardFilterContext";

/**
 * Preset filter cepat. days = 0 berarti "Hari ini saja" (start=end=today WIB).
 * Lainnya: range = today-N hari s/d today.
 */
const PRESETS = [
  { label: "Hari ini", days: 0 },
  { label: "7 hari", days: 7 },
  { label: "14 hari", days: 14 },
  { label: "30 hari", days: 30 },
];

export default function DateRangePicker() {
  const { startDate, endDate, setRange, minDate, maxDate } =
    useDashboardFilter();

  const today = todayStr();

  // Cek preset mana yang lagi aktif:
  //   days=0 -> startDate==today && endDate==today (hanya hari ini)
  //   days>0 -> endDate==today && startDate==today-Ndays
  const activePreset = PRESETS.find((p) => {
    if (p.days === 0) return startDate === today && endDate === today;
    return endDate === today && startDate === daysAgo(p.days);
  })?.days;

  // "Reset" = full range valid (Jan 1 - Mei 31, 2026), bukan kosong.
  const isFullRange = startDate === minDate && endDate === maxDate;

  const handlePresetClick = (days: number) => {
    if (days === 0) {
      // "Hari ini" -> start=end=today (cuma berita hari ini)
      setRange(today, today);
    } else {
      setRange(daysAgo(days), today);
    }
  };

  const handleReset = () => {
    // Default ke seluruh range valid biar field gak kosong (dd/mm/yyyy)
    setRange(minDate, maxDate);
  };

  return (
    <div className="flex flex-wrap items-center gap-2 p-3 rounded-lg bg-white border border-border text-black">
      <div className="flex items-center gap-1.5 text-black">
        <Calendar size={14} />
        <span className="text-xs font-medium">Filter tanggal:</span>
      </div>

      {/* Preset shortcut */}
      <div className="flex items-center gap-1">
        {PRESETS.map((p) => (
          <button
            key={p.days}
            type="button"
            onClick={() => handlePresetClick(p.days)}
            className={`px-2.5 py-1 text-xs rounded-md transition border ${
              activePreset === p.days
                ? "bg-blue-100 text-blue-700 border-blue-300"
                : "bg-white text-black border-border hover:text-black hover:border-foreground/30"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Custom range — constrained ke MIN..MAX */}
      <div className="flex items-center gap-1.5">
        <input
          type="date"
          value={startDate || ""}
          min={minDate}
          max={endDate || maxDate}
          onChange={(e) => setRange(e.target.value || null, endDate)}
          className="px-2 py-1 text-xs rounded-md bg-white border border-border text-black focus:outline-none focus:ring-1 focus:ring-primary"
        />
        <span className="text-xs text-black">s/d</span>
        <input
          type="date"
          value={endDate || ""}
          min={startDate || minDate}
          max={maxDate}
          onChange={(e) => setRange(startDate, e.target.value || null)}
          className="px-2 py-1 text-xs rounded-md bg-white border border-border text-black focus:outline-none focus:ring-1 focus:ring-primary"
        />
      </div>

      {/* Reset: kembali ke full range valid (Jan 1 - Mei 31, 2026) */}
      <button
        type="button"
        onClick={handleReset}
        disabled={isFullRange}
        title={
          isFullRange
            ? "Sudah menampilkan seluruh range (Apr 1 - Mei 31, 2026)"
            : "Reset ke seluruh range valid (Apr 1 - Mei 31, 2026)"
        }
        className="ml-auto flex items-center gap-1 px-2 py-1 text-xs rounded-md text-black hover:text-black hover:bg-white transition disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-black"
      >
        <RotateCcw size={12} />
        Reset
      </button>
    </div>
  );
}