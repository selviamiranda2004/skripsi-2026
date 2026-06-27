"""
DB migration: tambah kolom sentiment per-metode di tabel mentions.

Perubahan (idempotent, aman dijalankan berkali-kali):
  - mentions.sentiment_lexicon  : hasil rule-based
  - mentions.sentiment_svm      : hasil SVM
  - mentions.sentiment_label    : ground truth manual (untuk eval)
  - index pada sentiment_label (ngambil unlabeled mentions cepet)

Backfill:
  - Kalau ada baris dengan sentiment_lexicon NULL, isi pakai analyze_sentiment_lexicon(title)
  - sentiment_svm NULL biarin (akan diisi pas mention baru masuk atau via /sentiment-compare/predict-all)

Cara pakai:
  cd backend
  python migrate_sentiment.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import get_db_connection, get_db_cursor
from sentiment.lexicon import analyze_sentiment_lexicon


SQL_ADD_COLUMNS = """
ALTER TABLE public.mentions
    ADD COLUMN IF NOT EXISTS sentiment_lexicon VARCHAR
        CHECK (sentiment_lexicon IN ('positif','negatif','netral')),
    ADD COLUMN IF NOT EXISTS sentiment_svm VARCHAR
        CHECK (sentiment_svm IN ('positif','negatif','netral')),
    ADD COLUMN IF NOT EXISTS sentiment_label VARCHAR
        CHECK (sentiment_label IN ('positif','negatif','netral'));
"""

SQL_INDEX_LABEL = """
CREATE INDEX IF NOT EXISTS idx_mentions_sentiment_label
    ON public.mentions (sentiment_label);
"""

SQL_INDEX_LEXICON = """
CREATE INDEX IF NOT EXISTS idx_mentions_sentiment_lexicon
    ON public.mentions (sentiment_lexicon);
"""

SQL_INDEX_SVM = """
CREATE INDEX IF NOT EXISTS idx_mentions_sentiment_svm
    ON public.mentions (sentiment_svm);
"""


def main() -> None:
    print("🔧 [migrate] add sentiment_lexicon / sentiment_svm / sentiment_label columns")

    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute(SQL_ADD_COLUMNS)
            cursor.execute(SQL_INDEX_LABEL)
            cursor.execute(SQL_INDEX_LEXICON)
            cursor.execute(SQL_INDEX_SVM)
            print("✅ kolom + index berhasil dibuat")

    # --------------------------------------------------------------
    # Backfill sentiment_lexicon untuk row lama (berdasar title)
    # --------------------------------------------------------------
    print("🔁 [migrate] backfill sentiment_lexicon untuk mention lama...")
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute(
                """
                SELECT id, title
                FROM mentions
                WHERE sentiment_lexicon IS NULL
                """
            )
            rows = cursor.fetchall()

            if not rows:
                print("   (tidak ada row yang perlu di-backfill)")
                return

            print(f"   memproses {len(rows)} row...")
            updated = 0
            for row in rows:
                lex = analyze_sentiment_lexicon(row["title"] or "")
                cursor.execute(
                    "UPDATE mentions SET sentiment_lexicon = %s WHERE id = %s",
                    (lex, row["id"]),
                )
                updated += 1

            print(f"✅ backfill selesai untuk {updated} mention")

    print("\n🎉 migrasi sentiment selesai.")
    print("   Selanjutnya jalankan: python train_sentiment.py")


if __name__ == "__main__":
    main()
