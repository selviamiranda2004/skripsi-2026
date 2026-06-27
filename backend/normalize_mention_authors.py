"""
Normalize mentions.author supaya SAMA PERSIS dengan news_sources.name
untuk setiap source_id. Hasilnya: jumlah DISTINCT mentions.author akan
sama dengan jumlah row di news_sources (karena 1 source_id = 1 name).

Kenapa perlu: flow ingest ambil author dari text title RSS (via
extract_source), yang bisa punya variasi case/spacing/titik berbeda
untuk publisher yang sama (misal "Kompas.com" vs "KOMPAS.com"). Tapi
semuanya nge-point ke source_id yang sama karena slug-nya sama. Jadi
variasi cuma di kolom text mentions.author, bukan relasi FK.

Script ini bikin author konsisten = name dari news_sources yang di-reference.

USAGE:
  python normalize_mention_authors.py            # interaktif
  python normalize_mention_authors.py --yes      # skip konfirmasi
  python normalize_mention_authors.py --dry-run  # preview saja
"""

import sys
from database import get_db_connection, get_db_cursor


def get_counts(cursor) -> dict:
    cursor.execute("SELECT COUNT(*) AS n FROM news_sources")
    total_sources = int(cursor.fetchone()["n"])

    cursor.execute(
        "SELECT COUNT(DISTINCT author) AS n FROM mentions "
        "WHERE author IS NOT NULL AND author <> ''"
    )
    distinct_authors = int(cursor.fetchone()["n"])

    cursor.execute("SELECT COUNT(DISTINCT source_id) AS n FROM mentions")
    distinct_source_ids = int(cursor.fetchone()["n"])

    # Berapa baris mentions yang author-nya beda dengan news_sources.name-nya
    cursor.execute(
        """
        SELECT COUNT(*) AS n
        FROM mentions m
        JOIN news_sources ns ON ns.id = m.source_id
        WHERE m.author IS DISTINCT FROM ns.name
        """
    )
    mismatch_rows = int(cursor.fetchone()["n"])

    return {
        "total_sources": total_sources,
        "distinct_authors": distinct_authors,
        "distinct_source_ids": distinct_source_ids,
        "mismatch_rows": mismatch_rows,
    }


def preview_variants(cursor, limit: int = 20) -> list[dict]:
    """List publisher yang punya >1 variasi author di mentions."""
    cursor.execute(
        """
        SELECT
          ns.id AS source_id,
          ns.name AS canonical_name,
          COUNT(DISTINCT m.author) AS variant_count,
          array_agg(DISTINCT m.author ORDER BY m.author) AS variants,
          COUNT(*) AS mention_count
        FROM mentions m
        JOIN news_sources ns ON ns.id = m.source_id
        WHERE m.author IS NOT NULL AND m.author <> ''
        GROUP BY ns.id, ns.name
        HAVING COUNT(DISTINCT m.author) > 1
        ORDER BY variant_count DESC, ns.name
        LIMIT %s
        """,
        (limit,),
    )
    return [dict(r) for r in cursor.fetchall()]


def normalize_authors(cursor) -> int:
    """
    Single UPDATE yang set mentions.author = news_sources.name via join.
    Atomic & cepat (1 round-trip ke DB).
    """
    cursor.execute(
        """
        UPDATE mentions m
        SET author = ns.name,
            updated_at = NOW()
        FROM news_sources ns
        WHERE m.source_id = ns.id
          AND m.author IS DISTINCT FROM ns.name
        """
    )
    return cursor.rowcount or 0


def main():
    skip_confirm = "--yes" in sys.argv or "-y" in sys.argv
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("NORMALIZE mentions.author -> news_sources.name")
    print("=" * 60)

    # Fase 1: laporan sebelum
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            before = get_counts(cursor)
            variants = preview_variants(cursor, limit=20)

    print("\nKondisi saat ini:")
    print(f"  Total news_sources             : {before['total_sources']}")
    print(f"  DISTINCT mentions.author       : {before['distinct_authors']}")
    print(f"  DISTINCT mentions.source_id    : {before['distinct_source_ids']}")
    print(f"  Mention rows dengan mismatch   : {before['mismatch_rows']}")

    if before["mismatch_rows"] == 0:
        print(
            "\nTidak ada mismatch. mentions.author sudah konsisten dengan news_sources.name."
        )
        return

    print(f"\nSample {len(variants)} publisher dengan >1 variasi author:")
    for row in variants:
        v_preview = ", ".join(f'"{v}"' for v in row["variants"][:5])
        extra = "" if len(row["variants"]) <= 5 else f" (+{len(row['variants']) - 5} lagi)"
        print(
            f"  [{row['source_id']:>4}] {row['canonical_name']:<30} "
            f"variants={row['variant_count']} mentions={row['mention_count']}"
        )
        print(f"           -> {v_preview}{extra}")

    if dry_run:
        print(
            "\n[DRY RUN] Tidak ada perubahan. "
            "Jalankan tanpa --dry-run untuk eksekusi."
        )
        return

    # Fase 2: konfirmasi
    if not skip_confirm:
        print()
        answer = (
            input(
                f"Normalize {before['mismatch_rows']} mention rows "
                f"(author -> news_sources.name)? (ketik 'yes' untuk lanjut): "
            )
            .strip()
            .lower()
        )
        if answer != "yes":
            print("Dibatalkan.")
            return

    # Fase 3: eksekusi
    print(f"\n>> Updating {before['mismatch_rows']} rows...")
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            updated = normalize_authors(cursor)
            after = get_counts(cursor)

    print(f">> Updated: {updated} rows")
    print("\nKondisi setelah normalize:")
    print(f"  Total news_sources             : {after['total_sources']}")
    print(f"  DISTINCT mentions.author       : {after['distinct_authors']}")
    print(f"  DISTINCT mentions.source_id    : {after['distinct_source_ids']}")
    print(f"  Mention rows dengan mismatch   : {after['mismatch_rows']}")

    if (
        after["mismatch_rows"] == 0
        and after["distinct_authors"] == after["total_sources"]
    ):
        print(
            "\nSelesai. mentions.author sekarang konsisten dengan news_sources.name "
            f"(keduanya {after['total_sources']} unik)."
        )
    else:
        print(
            "\nMasih ada mismatch — coba jalankan ulang, "
            "atau ada insert concurrent yang masih berlangsung."
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDibatalkan oleh user (Ctrl+C).")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
