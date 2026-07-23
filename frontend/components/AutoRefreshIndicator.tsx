"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, RefreshCw, AlertCircle, AlertTriangle, Check } from "lucide-react";
import type { AutoRefreshState } from "@/hooks/useAutoRefreshNews";

interface Props {
  state: AutoRefreshState;
}

function formatTime(d: Date | null) {
  if (!d) return "-";
  return d.toLocaleTimeString("id-ID", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Format detik jadi readable: 3540 -> "59m 0s", 45 -> "45s" */
function formatDuration(sec: number) {
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return s === 0 ? `${m}m` : `${m}m ${s}s`;
}

/** Format interval jadi label readable: 3600 -> "1 jam", 60 -> "1 menit" */
function formatInterval(sec: number) {
  if (sec >= 3600) {
    const h = sec / 3600;
    return h === 1 ? "1 jam" : `${h} jam`;
  }
  if (sec >= 60) {
    const m = sec / 60;
    return m === 1 ? "1 menit" : `${m} menit`;
  }
  return `${sec} detik`;
}

/**
 * Indikator status auto-refresh untuk admin header.
 * Tampil di semua halaman admin (dashboard, users, mentions, sentiment).
 *
 * State:
 *  - hijau pulse  -> auto-refresh aktif, menunggu countdown
 *  - biru spinner -> sedang fetching mentions terbaru
 *  - merah        -> error pada refresh terakhir
 */
export default function AutoRefreshIndicator({ state }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const {
    isRefreshing,
    lastRefreshAt,
    secondsUntilNext,
    error,
    warning,
    lastTotal,
    refreshNow,
    intervalSec,
  } = state;

  // Pilih warna & label berdasar status:
  //   error    -> hard fail (HTTP error / timeout / backend down)
  //   warning  -> non-fatal (RSS kosong karena DNS / Google News blok)
  //   loading  -> sedang refresh
  //   active   -> idle, countdown ke refresh berikutnya
  const status = error
    ? "error"
    : isRefreshing
    ? "loading"
    : warning
    ? "warning"
    : "active";

  const statusStyle = {
    active: "bg-green-500/10 border-green-500/30 text-green-400",
    loading: "bg-blue-500/10 border-blue-500/30 text-blue-400",
    warning: "bg-amber-500/10 border-amber-500/30 text-amber-400",
    error: "bg-red-500/10 border-red-500/30 text-red-400",
  }[status];

  const dotStyle = {
    active: "bg-green-500",
    loading: "bg-blue-500",
    warning: "bg-amber-500",
    error: "bg-red-500",
  }[status];

  return (
    <div
      ref={rootRef}
      className="relative w-full sm:w-auto"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        disabled={isRefreshing}
        title="Lihat status auto refresh"
        className={`inline-flex w-auto max-w-full items-center justify-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1 sm:py-1.5 rounded-md sm:rounded-full border text-[10px] sm:text-xs font-medium transition ${statusStyle} hover:brightness-125 disabled:opacity-70 disabled:cursor-wait whitespace-nowrap self-start shrink-0`}
      >
        {/* Dot indicator */}
        <span className="relative flex h-2 w-2">
          {status === "active" && (
            <span
              className={`absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping ${dotStyle}`}
            />
          )}
          <span
            className={`relative inline-flex h-2 w-2 rounded-full ${dotStyle}`}
          />
        </span>

        {/* Label */}
        {isRefreshing ? (
          <span className="flex items-center gap-1 sm:gap-1.5 min-w-0">
            <Loader2 size={12} className="animate-spin shrink-0" />
            <span className="hidden sm:inline">Mengambil mentions...</span>
            <span className="sm:hidden">{formatDuration(secondsUntilNext)}</span>
          </span>
        ) : error ? (
          <span className="flex items-center gap-1 sm:gap-1.5 min-w-0">
            <AlertCircle size={12} className="shrink-0" />
            <span className="hidden sm:inline">Refresh gagal</span>
            <span className="sm:hidden">Err</span>
          </span>
        ) : warning ? (
          <span className="flex items-center gap-1 sm:gap-1.5 min-w-0">
            <AlertTriangle size={12} className="shrink-0" />
            <span className="hidden sm:inline">Tidak ada data baru</span>
            <span className="sm:hidden">Warn</span>
          </span>
        ) : (
          <span className="flex items-center gap-1 sm:gap-1.5 min-w-0">
            <RefreshCw size={12} className="shrink-0" />
            <span className="hidden sm:inline">Auto • {formatDuration(secondsUntilNext)}</span>
            <span className="sm:hidden">{formatDuration(secondsUntilNext)}</span>
          </span>
        )}
      </button>

      {/* Tooltip card on hover */}
      {open && (
        <div className="absolute right-0 top-full mt-2 w-[240px] sm:w-64 max-w-[calc(100vw-2rem)] z-50 bg-card border border-border rounded-lg shadow-xl p-3 text-xs">
          <div className="flex items-center gap-2 mb-2">
            <span className={`h-2 w-2 rounded-full ${dotStyle}`} />
            <span className="font-semibold text-foreground">
              {status === "active" && "Auto-refresh aktif"}
              {status === "loading" && "Sedang refresh"}
              {status === "warning" && "Refresh sukses, tapi kosong"}
              {status === "error" && "Refresh terakhir gagal"}
            </span>
          </div>

          <div className="space-y-1.5 text-muted-foreground">
            <div className="flex justify-between">
              <span>Interval</span>
              <span className="text-foreground">{formatInterval(intervalSec)}</span>
            </div>
            <div className="flex justify-between">
              <span>Refresh berikutnya</span>
              <span className="text-foreground">
                {isRefreshing ? "Sekarang..." : formatDuration(secondsUntilNext)}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Refresh terakhir</span>
              <span className="text-foreground">
                {formatTime(lastRefreshAt)}
              </span>
            </div>
            {lastTotal !== null && (
              <div className="flex justify-between">
                <span>Mention baru</span>
                <span className="flex items-center gap-1 text-foreground">
                  <Check size={12} className="text-green-500" />
                  {lastTotal}
                </span>
              </div>
            )}
            {error && (
              <div className="mt-2 p-2 rounded bg-red-500/10 text-red-400 border border-red-500/20">
                {error}
              </div>
            )}
            {!error && warning && (
              <div className="mt-2 p-2 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                {warning}
              </div>
            )}
          </div>

          {/* Manual refresh button — biar lebih obvious */}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              refreshNow();
            }}
            disabled={isRefreshing}
            className="mt-3 w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded bg-primary/10 hover:bg-primary/20 text-primary text-xs font-medium transition disabled:opacity-50 disabled:cursor-wait"
          >
            <RefreshCw size={12} className={isRefreshing ? "animate-spin" : ""} />
            {isRefreshing ? "Sedang refresh..." : "Refresh sekarang"}
          </button>

          <p className="mt-2 pt-2 border-t border-border text-[10px] text-muted-foreground">
            Mentions auto-refresh tiap {formatInterval(intervalSec)}.
            Klik tombol di atas untuk refresh manual.
          </p>
        </div>
      )}
    </div>
  );
}
