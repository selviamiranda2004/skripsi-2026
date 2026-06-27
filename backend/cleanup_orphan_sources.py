"""
Hapus news_sources yang tidak punya mention referensi (orphan).

Tujuan: sinkronkan jumlah row di tabel `news_sources` dengan distinct
`author` di tabel `mentions`. Orphan biasanya muncul karena:
  - reset_data.py TRUNCATE mentions tapi TIDAK menghapus news_sources
  - mention lama dihapus manual tapi news_sources-nya ditinggal
  - test/migrasi yang bikin source tanpa mention

Aman: cuma hapus row yang TIDAK di-reference oleh tabel mentions.
FK mentions.source_id -> news_sources(id) tidak akan terlanggar.

USAGE:
  python cleanup_orphan_sources.py           # interaktif (minta konfirmasi)
  python cleanup_orphan_sources.py --yes     # skip konfirmasi
  python cleanup_orphan_sources.py --dry-run # cuma preview, gak execute
"""

import sys
from database import get_db_connection, get_db_cursor


def get_counts(cursor) -> dict:
    """Ambil count news_sources + distinct author mentions untuk laporan."""
    cursor.execute("SELECT COUNT(*) AS n FROM news_sources")
    total_sources = int(cursor.fetchone()["n"])

    cursor.execute(
        "SELECT COUNT(DISTINCT author) AS n FROM mentions WHERE author IS NOT NULL AND author <> ''"
    )
    distinct_authors = int(cursor.fetchone()["n"])

    cursor.execute(
        "SELECT COUNT(DISTINCT source_id) AS n FROM mentions"
    )
    distinct_source_ids = int(cursor.fetchone()["n"])

    cursor.execute(
        """
        SELECT COUNT(*) AS n
        FROM news_sources
        WHERE id NOT IN (SELECT DISTINCT source_id FROM mentions)
        """
    )
    orphan_count = int(cursor.fetchone()["n"])

    return {
        "total_sources": total_sources,
        "distinct_authors": distinct_authors,
        "distinct_source_ids": distinct_source_ids,
        "orphan_count": orphan_count,
    }


def preview_orphans(cursor, limit: int = 20) -> list[dict]:
    """Ambil sample orphan untuk preview ke user."""
    cursor.execute(
        """
        SELECT id, name, slug
        FROM news_sources
        WHERE id NOT IN (SELECT DISTINCT source_id FROM mentions)
        ORDER BY name
        LIMIT %s
        """,
        (limit,),
    )
    return [dict(r) for r in cursor.fetchall()]


def delete_orphans(cursor) -> int:
    """Execute DELETE, return jumlah row yang dihapus."""
    cursor.execute(
        """
        DELETE FROM news_sources
        WHERE id NOT IN (SELECT DISTINCT source_id FROM mentions)
        """
    )
    return cursor.rowcount or 0


def main():
    skip_confirm = "--yes" in sys.argv or "-y" in sys.argv
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("CLEANUP ORPHAN news_sources")
    print("=" * 60)

    # === Fase 1: laporan sebelum ===
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            before = get_counts(cursor)
            orphans_preview = preview_orphans(cursor, limit=20)

    print("\nKondisi saat ini:")
    print(f"  Total news_sources         : {before['total_sources']}")
    print(f"  Distinct mentions.author   : {before['distinct_authors']}")
    print(f"  Distinct mentions.source_id: {before['distinct_source_ids']}")
    print(f"  Orphan (akan dihapus)      : {before['orphan_count']}")

    if before["orphan_count"] == 0:
        print("\nTidak ada orphan. news_sources sudah sinkron dengan mentions.")
        return

    print(f"\nSample {len(orphans_preview)} orphan (maks 20 pertama, urut nama):")
    for row in orphans_preview:
        print(f"  - [{row['id']:>4}] {row['name']} ({row['slug']})")
    if before["orphan_count"] > len(orphans_preview):
        print(f"  ... dan {before['orphan_count'] - len(orphans_preview)} lainnya")

    if dry_run:
        print("\n[DRY RUN] Tidak ada perubahan dilakukan. Jalankan tanpa --dry-run untuk eksekusi.")
        return

    # === Fase 2: konfirmasi ===
    if not skip_confirm:
        print()
        answer = input(
            f"Hapus {before['orphan_count']} orphan news_sources? (ketik 'yes' untuk lanjut): "
        ).strip().lower()
        if answer != "yes":
            print("Dibatalkan.")
            return

    # === Fase 3: eksekusi ===
    print(f"\n>> Menghapus {before['orphan_count']} orphan...")
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            deleted = delete_orphans(cursor)
            after = get_counts(cursor)

    print(f">> Deleted: {deleted} rows")
    print("\nKondisi setelah cleanup:")
    print(f"  Total news_sources         : {after['total_sources']}")
    print(f"  Distinct mentions.author   : {after['distinct_authors']}")
    print(f"  Distinct mentions.source_id: {after['distinct_source_ids']}")
    print(f"  Orphan tersisa             : {after['orphan_count']}")

    if after["orphan_count"] == 0:
        print("\nSelesai. news_sources sudah sinkron dengan mentions.")
    else:
        print(f"\nMasih ada {after['orphan_count']} orphan (mungkin ada insert concurrent).")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDibatalkan oleh user (Ctrl+C).")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
