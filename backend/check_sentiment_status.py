"""Check status migrasi SVM. Read-only, aman dijalankan kapan saja."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import get_db_cursor

with get_db_cursor() as cursor:
    cursor.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE sentiment IS NOT NULL)         AS sentiment_filled,
            COUNT(*) FILTER (WHERE sentiment_lexicon IS NOT NULL) AS lex_filled,
            COUNT(*) FILTER (WHERE sentiment_svm IS NOT NULL)     AS svm_filled,
            COUNT(*) FILTER (WHERE sentiment_label IS NOT NULL)   AS labeled,
            COUNT(*) FILTER (
                WHERE sentiment = sentiment_svm AND sentiment_svm IS NOT NULL
            ) AS sent_match_svm,
            COUNT(*) FILTER (
                WHERE sentiment = sentiment_lexicon AND sentiment_lexicon IS NOT NULL
            ) AS sent_match_lex
        FROM mentions
    """)
    r = cursor.fetchone()

print("=" * 50)
print(" STATUS MENTIONS SENTIMENT")
print("=" * 50)
print(f" total mentions      : {r['total']}")
print(f" kolom sentiment     : {r['sentiment_filled']} terisi")
print(f" sentiment_lexicon   : {r['lex_filled']} terisi")
print(f" sentiment_svm       : {r['svm_filled']} terisi")
print(f" sentiment_label     : {r['labeled']} (ground truth manual)")
print()
print(" Sumber kolom 'sentiment' (yang dipakai dashboard):")
print(f"   match SVM     : {r['sent_match_svm']}")
print(f"   match Lexicon : {r['sent_match_lex']}")

if r['total'] == 0:
    print("\n ⚠️  DB kosong, belum ada mention.")
elif r['sent_match_svm'] > r['sent_match_lex']:
    print("\n ✅ Mode aktif: SVM (sebagian besar pakai SVM)")
elif r['sent_match_lex'] > r['sent_match_svm']:
    print("\n ⚠️  Mode aktif: LEXICON. Belum full SVM.")
    print("    Jalankan: python setup_full_svm.py")
else:
    print("\n ⚠️  Mode aktif: campuran")
