from __future__ import annotations
 
import logging
from pathlib import Path
 
import pandas as pd
 
from .lexicon import analyze_sentiment_lexicon  # for silver labels (optional)
 
logger = logging.getLogger(__name__)
 
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
    Ambil mention yang sudah punya sentiment_label manual dari database.
 
    Ini adalah data yang dilabeli manual oleh peneliti lewat halaman
    Train SVM (dashboard admin) — dan merupakan angka yang dilaporkan
    sebagai "data berlabel manual" di narasi skripsi (contoh: 749 data).
 
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
    dropped_classes = set(counts.index) - set(keep)
    if dropped_classes:
        logger.warning(
            "load_db_labels: kelas %s dibuang karena jumlahnya < min_per_class=%d",
            dropped_classes, min_per_class,
        )
    df = df[df["label"].isin(keep)]
    return df.reset_index(drop=True)
 
 
# ---------------------------------------------------------------------------
# Combined loader
# ---------------------------------------------------------------------------
def load_training_data(
    include_db_labels: bool = True,
    seed_path: Path = SEED_CSV,
    use_seed: bool = True,
    verbose: bool = True,
) -> tuple[pd.DataFrame, dict]:
    """
    Bangun dataset training final.
 
    Parameters
    ----------
    include_db_labels : bool
        Kalau True, gabungkan data DB (label manual peneliti) ke dataset.
    seed_path : Path
        Lokasi file CSV seed. Kalau file tidak ada, seed dianggap kosong.
    use_seed : bool
        Kalau False, seed CSV SAMA SEKALI TIDAK dipakai — dataset training
        murni dari data DB saja. Gunakan opsi ini kalau ingin memastikan
        angka training/testing 100% konsisten dengan angka "data berlabel
        manual" yang dilaporkan di skripsi (mis. tepat 749, bukan 873).
    verbose : bool
        Kalau True, cetak ringkasan komposisi dataset ke log/console.
 
    Returns
    -------
    (DataFrame gabungan, info dict berisi rincian komposisi dataset)
    """
    if use_seed:
        try:
            seed_df = load_seed_dataset(seed_path)
        except FileNotFoundError:
            seed_df = pd.DataFrame(columns=["text", "label"])
    else:
        seed_df = pd.DataFrame(columns=["text", "label"])
 
    info: dict = {
        "use_seed": use_seed,
        "seed_rows": len(seed_df),
        "seed_distribution": seed_df["label"].value_counts().to_dict() if len(seed_df) else {},
        "db_rows": 0,
        "db_distribution": {},
        "duplicate_rows_dropped": 0,
        "total_rows": len(seed_df),
    }
 
    combined = seed_df
 
    if include_db_labels:
        db_df = load_db_labels()
        if len(db_df) > 0:
            info["db_rows"] = len(db_df)
            info["db_distribution"] = db_df["label"].value_counts().to_dict()
 
            before_dedup = len(seed_df) + len(db_df)
            combined = pd.concat([seed_df, db_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=["text"], keep="last")
            after_dedup = len(combined)
 
            info["duplicate_rows_dropped"] = before_dedup - after_dedup
            info["total_rows"] = after_dedup
 
    if verbose:
        _log_dataset_summary(info)
 
    return combined.reset_index(drop=True), info
 
 
def _log_dataset_summary(info: dict) -> None:
    """Cetak ringkasan komposisi dataset supaya jumlah data selalu jelas."""
    msg = (
        "\n"
        "==================== KOMPOSISI DATASET TRAINING ====================\n"
        f"  Seed CSV dipakai      : {info['use_seed']}\n"
        f"  Jumlah data seed      : {info['seed_rows']}  {info['seed_distribution']}\n"
        f"  Jumlah data DB (manual): {info['db_rows']}  {info['db_distribution']}\n"
        f"  Duplikat dibuang       : {info['duplicate_rows_dropped']}\n"
        f"  TOTAL DATA TRAINING    : {info['total_rows']}\n"
        "======================================================================\n"
        "  ⚠️  Kalau total_rows berbeda dari angka 'data berlabel manual' yang\n"
        "      dilaporkan di skripsi, cek apakah use_seed=True menyebabkan\n"
        "      seed CSV ikut ditambahkan ke dataset training.\n"
        "======================================================================"
    )
    print(msg)
    logger.info(msg)
 
 
def describe_training_data(
    seed_path: Path = SEED_CSV,
    include_db_labels: bool = True,
) -> dict:
    """
    Cek cepat komposisi dataset TANPA menjalankan training.
 
    Cocok dipanggil dari terminal/notebook sebelum retrain, untuk
    memastikan angka training konsisten dengan yang dilaporkan di skripsi.
 
    Contoh pemakaian:
        python -c "from sentiment.dataset import describe_training_data; \
                    describe_training_data()"
    """
    _, info_with_seed = load_training_data(
        include_db_labels=include_db_labels,
        seed_path=seed_path,
        use_seed=True,
        verbose=False,
    )
    _, info_without_seed = load_training_data(
        include_db_labels=include_db_labels,
        seed_path=seed_path,
        use_seed=False,
        verbose=False,
    )
 
    summary = {
        "dengan_seed": info_with_seed,
        "tanpa_seed": info_without_seed,
        "selisih_total_rows": info_with_seed["total_rows"] - info_without_seed["total_rows"],
    }
 
    print("\n=== PERBANDINGAN: DENGAN SEED vs TANPA SEED ===")
    print(f"Total data DENGAN seed  : {info_with_seed['total_rows']}")
    print(f"Total data TANPA seed   : {info_without_seed['total_rows']}")
    print(f"Selisih (kontribusi seed): {summary['selisih_total_rows']}")
    print("=================================================\n")
 
    return summary
 
 
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