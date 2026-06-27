"""Backfill sentiment_svm untuk row yang masih NULL + sync kolom sentiment."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import get_db_connection, get_db_cursor
from sentiment.svm import load_default_model

print("=" * 60)
print(" 🔄 BACKFILL SVM + SYNC kolom 'sentiment' ke FULL SVM")
print("=" * 60)

model = load_default_model()
if model is None:
    print("❌ Model SVM tidak ditemukan. Jalankan: python train_sentiment.py")
    sys.exit(1)

with get_db_connection() as conn:
    with get_db_cursor(conn) as cursor:
        # 1) Predict ulang row yang sentiment_svm NULL
        cursor.execute("SELECT id, title FROM mentions WHERE sentiment_svm IS NULL")
        null_rows = cursor.fetchall()
        if null_rows:
            print(f"   - ada {len(null_rows)} row sentiment_svm NULL, predicting...")
            titles = [r["title"] or "" for r in null_rows]
            preds = model.predict(titles)
            for row, pred in zip(null_rows, preds):
                cursor.execute(
                    "UPDATE mentions SET sentiment_svm = %s WHERE id = %s",
                    (pred, row["id"]),
                )
            print(f"   ✅ {len(null_rows)} row di-fill SVM")
        else:
            print("   ✅ tidak ada row dengan sentiment_svm NULL")

        # 2) Sync kolom sentiment (active) = sentiment_svm di SEMUA row
        cursor.execute("""
            UPDATE mentions
            SET sentiment = sentiment_svm,
                updated_at = NOW()
            WHERE sentiment_svm IS NOT NULL
              AND (sentiment IS DISTINCT FROM sentiment_svm)
        """)
        synced = cursor.rowcount
        print(f"   ✅ {synced} row kolom 'sentiment' di-sync ke SVM")

        # 3) Final check
        cursor.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE sentiment = sentiment_svm) AS match_svm,
                COUNT(*) FILTER (WHERE sentiment_svm IS NULL) AS still_null
            FROM mentions
        """)
        s = cursor.fetchone()
        print()
        print("=" * 60)
        print(f" total mentions     : {s['total']}")
        print(f" sentiment = SVM    : {s['match_svm']}")
        print(f" sentiment_svm NULL : {s['still_null']}")
        print("=" * 60)
        if s["match_svm"] == s["total"]:
            print(" 🎉 FULL SVM MODE: 100% mentions pakai prediksi SVM")
        else:
            diff = s["total"] - s["match_svm"]
            print(f" ⚠️  masih ada {diff} row yang belum sinkron")
