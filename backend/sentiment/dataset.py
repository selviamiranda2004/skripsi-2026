"""
Dataset loader untuk training SVM sentiment.

Sumber data:
  1. Bundled CSV: backend/data/sentiment_seed.csv  (text,label)
  2. DB column  : mentions.sentiment_label (manual ground truth, optional)

Kalau DB punya >= MIN_DB_LABELS row berlabel, gabungkan keduanya.
Ini supaya model bisa "belajar" dari koreksi user lewat labeling UI.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .lexicon import analyze_sentiment_lexicon  # for silver labels (optional)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEED_CSV = DATA_DIR / "sentiment_seed.csv"

VALID_LABELS = {"positif", "negatif", "netral"}


# ---------------------------------------------------------------------------
# Bundled seed dataset
# ---------------------------------------------------------------------------
def load_seed_dataset(path: Path = SEED_CSV) -> pd.DataFrame:
    """Load bundled CSV. Format: kolom 'text' + 'label'."""
    if not path.exists():
        raise FileNotFoundError(
            f"Seed dataset tidak ditemukan di {path}. "
            "Pastikan backend/data/sentiment_seed.csv ada."
        )
    df = pd.read_csv(path)
    df = _validate(df, source=str(path))
    return df


# ---------------------------------------------------------------------------
# DB labels (manual ground truth dari labeling UI)
# ---------------------------------------------------------------------------
def load_db_labels(min_per_class: int = 5) -> pd.DataFrame:
    """
    Ambil mention yang sudah punya sentiment_label manual.
    Kembalikan DataFrame[text,label] atau DataFrame kosong kalau belum cukup.
    """
    try:
        from database import get_db_cursor  # local import to avoid cycle
    except ImportError:
        return pd.DataFrame(columns=["text", "label"])

    sql = """
        SELECT title AS text, sentiment_label AS label
        FROM mentions
        WHERE sentiment_label IS NOT NULL
          AND sentiment_label IN ('positif','negatif','netral')
          AND title IS NOT NULL
        ORDER BY id
    """
    with get_db_cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()

    if not rows:
        return pd.DataFrame(columns=["text", "label"])

    df = pd.DataFrame([dict(r) for r in rows])
    # Drop classes that don't have enough examples
    counts = df["label"].value_counts()
    keep = counts[counts >= min_per_class].index
    df = df[df["label"].isin(keep)]
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Combined loader
# ---------------------------------------------------------------------------
def load_training_data(
    include_db_labels: bool = True,
    seed_path: Path = SEED_CSV,
) -> tuple[pd.DataFrame, dict]:
    try:
        seed_df = load_seed_dataset(seed_path)
    except FileNotFoundError:
        seed_df = pd.DataFrame(columns=["text", "label"])

    info: dict = {
        "seed_rows": len(seed_df),
        "seed_distribution": seed_df["label"].value_counts().to_dict(),
        "db_rows": 0,
        "db_distribution": {},
        "total_rows": len(seed_df),
    }

    if include_db_labels:
        db_df = load_db_labels()
        if len(db_df) > 0:
            info["db_rows"] = len(db_df)
            info["db_distribution"] = db_df["label"].value_counts().to_dict()
            combined = pd.concat([seed_df, db_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=["text"], keep="last")
            info["total_rows"] = len(combined)
            return combined, info

    return seed_df, info


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------
def _validate(df: pd.DataFrame, source: str) -> pd.DataFrame:
    if "text" not in df.columns or "label" not in df.columns:
        raise ValueError(f"{source} harus punya kolom 'text' dan 'label'")
    df = df.dropna(subset=["text", "label"]).copy()
    df["text"] = df["text"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip().str.lower()
    df = df[df["label"].isin(VALID_LABELS)]
    df = df[df["text"].str.len() > 0]
    if len(df) == 0:
        raise ValueError(f"{source} kosong setelah validasi")
    return df.reset_index(drop=True)
