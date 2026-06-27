"use client";

import { useMemo, useState, useEffect } from "react";
import useSWR, { mutate } from "swr";
import { fetcher, BASE_URL } from "@/services/api";
import {
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Brain,
  Filter,
  Loader2,
  Sparkles,
  Wand2,
} from "lucide-react";

type Sentiment = "positif" | "negatif" | "netral";

interface SampleItem {
  id: number;
  title: string;
  author: string | null;
  url: string | null;
  sentiment_svm: Sentiment | null;
  sentiment_label: Sentiment | null;
  date: string;
}

interface SampleResp {
  items: SampleItem[];
  svm_available: boolean;
}

interface ConfusionMatrix {
  labels: Sentiment[];
  matrix: number[][];
}

interface MetricsBlock {
  support: number;
  accuracy: number;
  macro: { precision: number; recall: number; f1: number };
  weighted: { precision: number; recall: number; f1: number };
  macro_f1: number;
  weighted_f1: number;
  per_class: Record<Sentiment, { precision: number; recall: number; f1: number; support: number }>;
  confusion_matrix: ConfusionMatrix;
}

interface MetricsResp {
  labeled_count: number;
  svm_available: boolean;
  metrics?: MetricsBlock;
  message?: string;
}

interface StatusResp {
  svm_available: boolean;
  total_mentions: number;
  svm_predicted: number;
  labeled: number;
}

interface TrainingMetricsResp {
  available: boolean;
  message?: string;
  metrics?: {
    svm: MetricsBlock;
    meta: { trained_at: string; data_info: any; trigger?: string };
  };
}

const STATUS_URL = `${BASE_URL}/svm/status`;
const METRICS_URL = `${BASE_URL}/svm/metrics`;
const TRAINING_URL = `${BASE_URL}/svm/training-metrics`;

const COLORS: Record<Sentiment, string> = {
  positif: "#22c55e",
  negatif: "#ef4444",
  netral: "#71717a",
};

const LABELS_ID: Record<Sentiment, string> = {
  positif: "Positif",
  negatif: "Negatif",
  netral: "Netral",
};

const getToken = () =>
  typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;

const fmtPct = (v?: number) =>
  v === undefined || v === null ? "—" : `${(v * 100).toFixed(1)}%`;

const SentimentPill = ({ value }: { value: Sentiment | null }) => {
  if (!value)
    return <span className="text-xs text-black italic">—</span>;
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
      style={{
        backgroundColor: `${COLORS[value]}20`,
        color: COLORS[value],
      }}
    >
      {LABELS_ID[value]}
    </span>
  );
};

function ConfusionMatrixView({ cm }: { cm: ConfusionMatrix }) {
  if (!cm) return null;
  const max = Math.max(1, ...cm.matrix.flat());
  return (
    <div className="overflow-x-auto">
      <table className="text-xs border-separate" style={{ borderSpacing: 0 }}>
        <thead>
          <tr>
            <th className="px-2 py-1 text-black">true ↓ / pred →</th>
            {cm.labels.map((l) => (
              <th key={l} className="px-2 py-1 font-semibold text-black">
                {LABELS_ID[l]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cm.matrix.map((row, i) => (
            <tr key={i}>
              <td className="px-2 py-1 font-semibold text-right text-black">
                {LABELS_ID[cm.labels[i]]}
              </td>
              {row.map((v, j) => {
                const intensity = v / max;
                return (
                  <td
                    key={j}
                    className="px-3 py-2 text-center font-mono border border-border text-black"
                    style={{
                      backgroundColor: `rgba(34, 197, 94, ${intensity * 0.5})`,
                    }}
                  >
                    {v}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MetricsCards({ m }: { m: MetricsBlock }) {
  const items = [
    { k: "Accuracy", v: m.accuracy, icon: CheckCircle2 },
    { k: "Precision (macro)", v: m.macro?.precision, icon: Brain },
    { k: "Recall (macro)", v: m.macro?.recall, icon: Brain },
    { k: "F1 (macro)", v: m.macro?.f1, icon: Brain },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {items.map((it) => (
        <div key={it.k} className="bg-white border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 text-black text-xs mb-1">
            <it.icon size={14} />
            {it.k}
          </div>
          <div className="text-2xl font-bold text-black">{fmtPct(it.v)}</div>
        </div>
      ))}
    </div>
  );
}

function QuickPredictBox() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<{ text: string; sentiment: Sentiment | null } | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!text.trim()) return;
    setLoading(true);
    try {
      const token = getToken();
      const r = await fetch(
        `${BASE_URL}/svm/predict?text=${encodeURIComponent(text)}`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Failed");
      setResult(data);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white border border-border rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2 font-semibold text-black">
        <Wand2 size={16} /> Quick Predict
      </div>
      <p className="text-xs text-black">
        Test prediksi SVM untuk text bebas (tidak menyentuh data DB).
      </p>
      <div className="flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Tulis kalimat berita untuk diprediksi..."
          className="flex-1 px-3 py-2 text-sm border border-border rounded-lg bg-white text-black"
        />
        <button
          onClick={submit}
          disabled={loading || !text.trim()}
          className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg disabled:opacity-50"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : "Predict"}
        </button>
      </div>
      {result && (
        <div className="text-sm flex items-center gap-2 pt-2 border-t border-border">
          <span className="text-black">Hasil:</span>
          <SentimentPill value={result.sentiment} />
        </div>
      )}
    </div>
  );
}

export default function SvmTrainingPage() {
  const [filterUnlabeled, setFilterUnlabeled] = useState(false);
  const [limit, setLimit] = useState(50);
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [retraining, setRetraining] = useState(false);
  const [testSize, setTestSize] = useState(0.2);
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" } | null>(null);

  const sampleQuery = useMemo(() => {
    const p = new URLSearchParams();
    p.set("limit", String(limit));
    if (filterUnlabeled) p.set("only_unlabeled", "true");
    return p.toString();
  }, [filterUnlabeled, limit]);

  const sampleUrl = `${BASE_URL}/svm/sample?${sampleQuery}`;

  const { data: sample, isLoading: sampleLoading } = useSWR<SampleResp>(sampleUrl, fetcher);
  const { data: metrics } = useSWR<MetricsResp>(METRICS_URL, fetcher);
  const { data: status } = useSWR<StatusResp>(STATUS_URL, fetcher);
  const { data: training } = useSWR<TrainingMetricsResp>(TRAINING_URL, fetcher);

  useEffect(() => {
    if (training?.metrics) {
      const split = (training.metrics as any)?.split;
      const cfgTestSize = (training.metrics as any)?.meta?.config?.test_size;
      const lastTestSize =
        typeof split?.test_size === "number"
          ? split.test_size
          : typeof cfgTestSize === "number"
          ? cfgTestSize
          : null;
      if (lastTestSize !== null) setTestSize(lastTestSize);
    }
  }, [training]);

  const refreshAll = () => {
    mutate(sampleUrl);
    mutate(METRICS_URL);
    mutate(STATUS_URL);
    mutate(TRAINING_URL);
  };

  const showToast = (msg: string, type: "success" | "error") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 2500);
  };

  const handleLabel = async (id: number, label: Sentiment | null) => {
    setUpdatingId(id);
    try {
      const token = getToken();
      const url = `${BASE_URL}/svm/labels/${id}`;
      const res = await fetch(url, {
        method: label ? "POST" : "DELETE",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: label ? JSON.stringify({ label }) : undefined,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal");
      showToast(label ? `Label di-set: ${LABELS_ID[label]}` : "Label dihapus", "success");
      refreshAll();
    } catch (e: any) {
      showToast(e.message, "error");
    } finally {
      setUpdatingId(null);
    }
  };

  const handleRetrain = async () => {
    const labeled = status?.labeled ?? 0;
    const trainPct = Math.round((1 - testSize) * 100);
    const testPct = Math.round(testSize * 100);
    const splitLabel = `${trainPct}:${testPct}`;
    const msg =
      labeled === 0
        ? `Anda belum pernah menambahkan label manual. Training akan pakai dataset bawaan saja dengan split ${splitLabel}. Lanjut?`
        : `Train ulang SVM pakai ${labeled} label manual + dataset bawaan (split ${splitLabel}), lalu apply ke seluruh data. Proses 5-30 detik. Lanjut?`;
    if (!confirm(msg)) return;

    setRetraining(true);
    try {
      const token = getToken();
      const res = await fetch(`${BASE_URL}/svm/retrain?test_size=${testSize}`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Retrain gagal");
      showToast(`Model di-train ulang (split ${splitLabel}). ${data.applied ?? 0} mention di-update.`, "success");
      refreshAll();
    } catch (e: any) {
      showToast(e.message, "error");
    } finally {
      setRetraining(false);
    }
  };

  const handleBackfill = async () => {
    if (!confirm("Predict ulang seluruh mention pakai model SVM saat ini?")) return;
    try {
      const token = getToken();
      const res = await fetch(`${BASE_URL}/svm/predict-all?repredict=true`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Predict-all gagal");
      showToast(`${data.updated ?? 0} mention di-predict ulang`, "success");
      refreshAll();
    } catch (e: any) {
      showToast(e.message, "error");
    }
  };

  const svmAvail = status?.svm_available ?? sample?.svm_available ?? false;
  const m = metrics?.metrics;
  const t = training?.metrics?.svm;

  return (
    <div className="space-y-6">
      {/* TOAST */}
      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-sm ${
            toast.type === "success" ? "bg-green-500 text-white" : "bg-red-500 text-white"
          }`}
        >
          {toast.msg}
        </div>
      )}

      {/* HEADER */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-black">Train SVM</h2>
        </div>
        <div className="flex gap-2 flex-wrap">
          {svmAvail && (
            <button
              onClick={handleBackfill}
              className="px-3 py-2 text-sm border border-border rounded-lg hover:bg-gray-100 flex items-center gap-2 text-black"
              title="Predict ulang seluruh data dengan model saat ini"
            >
              <Brain size={14} /> Predict Ulang Semua
            </button>
          )}
          <div className="flex items-center gap-1 px-2 py-1 border border-border rounded-lg">
            <label htmlFor="split-ratio" className="text-xs text-black">
              Split:
            </label>
            <select
              id="split-ratio"
              value={testSize}
              onChange={(e) => setTestSize(parseFloat(e.target.value))}
              disabled={retraining}
              className="text-sm bg-white text-black outline-none cursor-pointer disabled:opacity-50"
              title="Rasio train:test untuk hold-out evaluation"
            >
              <option value={0.2} style={{ color: "black" }}>80:20</option>
              <option value={0.3} style={{ color: "black" }}>70:30</option>
              <option value={0.5} style={{ color: "black" }}>50:50</option>
            </select>
          </div>
          <button
            onClick={handleRetrain}
            disabled={retraining}
            className="px-3 py-2 text-sm bg-primary text-primary-foreground rounded-lg disabled:opacity-50 flex items-center gap-2"
          >
            {retraining ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
            Retrain SVM
          </button>
        </div>
      </div>

      {/* SVM STATUS BANNER */}
      {!svmAvail ? (
        <div className="bg-amber-500/10 border border-amber-500/30 text-amber-600 rounded-lg p-3 text-sm flex items-center gap-2">
          <AlertCircle size={16} />
          Model SVM belum di-train. Klik <strong>Retrain SVM</strong> untuk training pertama kali (dataset bawaan sudah disiapkan).
        </div>
      ) : (
        <div className="bg-blue-500/10 border border-blue-500/30 text-blue-600 rounded-lg p-3 text-sm flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Brain size={16} />
            <span>
              <strong>Mode aktif:</strong> SVM (semua sentiment di dashboard dari model machine learning)
            </span>
          </div>
          {status && (
            <span className="text-xs opacity-80">
              {status.total_mentions} mention · {status.svm_predicted} ada prediksi SVM · {status.labeled} sudah dilabel manual
            </span>
          )}
        </div>
      )}

      {/* WORKFLOW GUIDE */}
      {svmAvail && (status?.labeled ?? 0) < 10 && (
        <div className="bg-white border border-border rounded-xl p-4 text-sm">
          <p className="font-semibold mb-2 flex items-center gap-2 text-black">
            <Sparkles size={14} /> Cara training SVM
          </p>
          <ol className="list-decimal list-inside space-y-1 text-black">
            <li>
              Scroll ke tabel di bawah, klik tombol <strong>Positif/Negatif/Netral</strong> di kolom <em>Set Label</em> untuk minimal ~10-30 mention.
            </li>
            <li>Klik <strong>Retrain SVM</strong> di pojok kanan atas. Tunggu 5-30 detik.</li>
            <li>Selesai. Mention baru yang masuk akan otomatis pakai model baru.</li>
          </ol>
        </div>
      )}

      {/* QUICK PREDICT */}
      <QuickPredictBox />

      {/* METRICS */}
      <section>
        <h3 className="text-lg font-semibold mb-1 text-black">Performa Model SVM</h3>
        <p className="text-xs text-black mb-3">
          Akurasi prediksi pada mention yang sudah Anda label manual.
        </p>
        {!metrics ? (
          <div className="text-sm text-black">Loading...</div>
        ) : !m ? (
          <div className="bg-white border border-border rounded-xl p-4 text-sm text-black">
            {metrics.message || "Belum ada label manual."}
          </div>
        ) : (
          <div className="space-y-4">
            <MetricsCards m={m} />
            <div className="bg-white border border-border rounded-xl p-4">
              <p className="text-sm font-semibold mb-2 text-black">
                Confusion Matrix (n = {status?.labeled ?? metrics.labeled_count})
              </p>
              <ConfusionMatrixView cm={m.confusion_matrix} />
            </div>
          </div>
        )}
      </section>

      {/* TRAINING METRICS */}
      {t && (
        <section>
          <h3 className="text-lg font-semibold mb-1 text-black">Performa Model pada Test Set</h3>
          <p className="text-xs text-black mb-3">
            {(() => {
              const split = (training?.metrics as any)?.split;
              const cfgTestSize = (training?.metrics as any)?.meta?.config?.test_size;
              const ts =
                typeof split?.test_size === "number"
                  ? split.test_size
                  : typeof cfgTestSize === "number"
                  ? cfgTestSize
                  : 0.2;
              const trainP = Math.round((1 - ts) * 100);
              const testP = Math.round(ts * 100);
              return (
                <>
                  Hold-out split <strong>{trainP}:{testP}</strong> ({testP}% test set).
                </>
              );
            })()}
            {training?.metrics?.meta?.trained_at && (
              <> Trained: {new Date(training.metrics.meta.trained_at).toLocaleString("id-ID")}</>
            )}
          </p>
          <MetricsCards m={t} />
        </section>
      )}

      {/* TABLE */}
      <section>
        <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
          <h3 className="text-lg font-semibold text-black">
            Mentions {filterUnlabeled && "(belum dilabel)"}
          </h3>
          <div className="flex gap-2 items-center">
            <label className="flex items-center gap-1 text-xs cursor-pointer text-black">
              <input
                type="checkbox"
                checked={filterUnlabeled}
                onChange={(e) => setFilterUnlabeled(e.target.checked)}
              />
              <Filter size={12} /> Hanya yang belum dilabel
            </label>
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="px-2 py-1 text-xs border border-border rounded bg-white text-black"
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
          </div>
        </div>

        <div className="bg-white border border-border rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 text-xs uppercase">
              <tr>
                <th className="px-3 py-2 text-left text-black">Title</th>
                <th className="px-3 py-2 text-left text-black">Date</th>
                <th className="px-3 py-2 text-center text-black">Prediksi SVM</th>
                <th className="px-3 py-2 text-center text-black">Label (truth)</th>
                <th className="px-3 py-2 text-center text-black">Set Label</th>
              </tr>
            </thead>
            <tbody>
              {sampleLoading && (
                <tr>
                  <td colSpan={5} className="px-3 py-6 text-center text-black">Loading...</td>
                </tr>
              )}
              {!sampleLoading && sample?.items.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-6 text-center text-black">
                    Tidak ada mention yang cocok filter.
                  </td>
                </tr>
              )}
              {sample?.items.map((row) => {
                const correct =
                  row.sentiment_label &&
                  row.sentiment_svm &&
                  row.sentiment_label === row.sentiment_svm;
                return (
                  <tr key={row.id} className="border-t border-border hover:bg-gray-50">
                    <td className="px-3 py-2 max-w-md">
                      {row.url ? (
                        <a
                          href={row.url}
                          target="_blank"
                          rel="noreferrer"
                          className="hover:underline line-clamp-2 text-black"
                        >
                          {row.title}
                        </a>
                      ) : (
                        <span className="line-clamp-2 text-black">{row.title}</span>
                      )}
                      {row.author && (
                        <p className="text-xs text-black mt-0.5">{row.author}</p>
                      )}
                    </td>
                    <td className="px-3 py-2 text-xs text-black whitespace-nowrap">{row.date}</td>
                    <td className="px-3 py-2 text-center">
                      <SentimentPill value={row.sentiment_svm} />
                    </td>
                    <td className="px-3 py-2 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <SentimentPill value={row.sentiment_label} />
                        {row.sentiment_label && correct === true && (
                          <span title="SVM benar" className="text-green-500">✓</span>
                        )}
                        {row.sentiment_label && correct === false && (
                          <span title="SVM salah" className="text-red-500">✗</span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex justify-center gap-1">
                        {(["positif", "netral", "negatif"] as Sentiment[]).map((s) => (
                          <button
                            key={s}
                            disabled={updatingId === row.id}
                            onClick={() => handleLabel(row.id, s)}
                            className={`px-2 py-1 text-xs rounded transition disabled:opacity-50 ${
                              row.sentiment_label === s ? "ring-2 ring-offset-1" : "hover:opacity-80"
                            }`}
                            style={{
                              backgroundColor: `${COLORS[s]}25`,
                              color: COLORS[s],
                            }}
                            title={`Set ${LABELS_ID[s]}`}
                          >
                            {s === "positif" ? "+" : s === "negatif" ? "−" : "○"}
                          </button>
                        ))}
                        {row.sentiment_label && (
                          <button
                            disabled={updatingId === row.id}
                            onClick={() => handleLabel(row.id, null)}
                            className="px-2 py-1 text-xs rounded text-black hover:bg-gray-100 disabled:opacity-50"
                            title="Hapus label"
                          >
                            ×
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}