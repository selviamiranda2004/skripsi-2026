"""
Evaluasi side-by-side antara dua metode sentiment (lexicon vs SVM)
terhadap ground truth manual.

Metrik yang dihitung:
  - accuracy
  - precision / recall / F1 (per kelas + macro & weighted)
  - confusion matrix (3x3 untuk positif/negatif/netral)
"""

from __future__ import annotations

from typing import Sequence

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)

LABELS = ["positif", "negatif", "netral"]


def evaluate_predictions(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    labels: list[str] = LABELS,
) -> dict:
    """
    Hitung metrik standar. Aman walau y_pred tidak punya semua kelas.
    """
    if len(y_true) == 0 or len(y_pred) == 0 or len(y_true) != len(y_pred):
        return {
            "support": 0,
            "accuracy": 0.0,
            "macro_f1": 0.0,
            "weighted_f1": 0.0,
            "per_class": {},
            "confusion_matrix": {"labels": labels, "matrix": []},
        }

    accuracy = float(accuracy_score(y_true, y_pred))

    # Per-class precision / recall / f1 / support
    p, r, f, s = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    per_class = {
        labels[i]: {
            "precision": float(p[i]),
            "recall": float(r[i]),
            "f1": float(f[i]),
            "support": int(s[i]),
        }
        for i in range(len(labels))
    }

    # Macro & weighted
    p_macro, r_macro, f_macro, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="macro", zero_division=0
    )
    p_w, r_w, f_w, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="weighted", zero_division=0
    )

    cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()

    return {
        "support": len(y_true),
        "accuracy": accuracy,
        "macro": {
            "precision": float(p_macro),
            "recall": float(r_macro),
            "f1": float(f_macro),
        },
        "weighted": {
            "precision": float(p_w),
            "recall": float(r_w),
            "f1": float(f_w),
        },
        "macro_f1": float(f_macro),
        "weighted_f1": float(f_w),
        "per_class": per_class,
        "confusion_matrix": {"labels": labels, "matrix": cm},
    }


def compare_methods(
    y_true: Sequence[str],
    y_lexicon: Sequence[str],
    y_svm: Sequence[str],
) -> dict:
    """
    Bandingkan dua metode terhadap ground truth yang sama.
    Return dict siap di-serialize ke JSON / kirim ke frontend.
    """
    return {
        "lexicon": evaluate_predictions(y_true, y_lexicon),
        "svm": evaluate_predictions(y_true, y_svm),
        "ground_truth_distribution": _distribution(y_true),
        "agreement_rate": _agreement(y_lexicon, y_svm),
    }


def _distribution(labels: Sequence[str]) -> dict[str, int]:
    out = {l: 0 for l in LABELS}
    for x in labels:
        if x in out:
            out[x] += 1
    return out


def _agreement(a: Sequence[str], b: Sequence[str]) -> float:
    if len(a) == 0 or len(a) != len(b):
        return 0.0
    same = sum(1 for x, y in zip(a, b) if x == y)
    return same / len(a)


def text_report(
    name: str,
    y_true: Sequence[str],
    y_pred: Sequence[str],
    labels: list[str] = LABELS,
) -> str:
    """Sklearn-style text report (untuk CLI output)."""
    header = f"\n=== {name.upper()} ===\n"
    return header + classification_report(
        y_true, y_pred, labels=labels, zero_division=0, digits=3
    )
