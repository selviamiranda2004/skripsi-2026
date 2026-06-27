"""
Reset data mentions di database.

Default — hapus data di tabel:
  - mentions
  - mention_keywords
  - sentiment_analysis

TIDAK menghapus:
  - users        (admin & user lain tetap aman)
  - keywords     (biar refresh-news langsung bisa relasi keyword)
  - news_sources (biar source default tetap ada)

Mode --all juga hapus keywords + news_sources + users NON-ADMIN.
User dengan role='admin' SELALU dipertahankan.

Pakai TRUNCATE ... RESTART IDENTITY CASCADE supaya:
  - Operasi ringan (1x WAL, bukan per-row)
  - Auto-increment ID balik ke 1
  - FK dependency otomatis ke-handle

USAGE:
  python reset_data.py            # interaktif, minta konfirmasi
  python reset_data.py --yes      # skip konfirmasi (untuk scripting)
  python reset_data.py --all      # WIPE keywords + news_sources + non-admin users juga
"""

import sys
from database import get_db_connection, get_db_cursor

# Default: tabel yang dibersihkan setiap reset
TABLES_TO_WIPE = [
    "mention_keywords",
    "sentiment_analysis",
    "mentions",
]

# Mode --all: tambahan tabel yang ikut dihapus (TRUNCATE)
EXTRA_FULL_WIPE = [
    "keywords",
    "news_sources",
]

# Tabel yang ditampilkan di laporan ketika --all (users dihapus parsial, bukan TRUNCATE)
ALL_DISPLAY_TABLES = TABLES_TO_WIPE + EXTRA_FULL_WIPE + ["users"]


def show_counts(label: str, tables: list[str]) -> None:
    """Cetak jumlah row per tabel untuk verifikasi."""
    print(f"\n{label}")
    print("-" * 40)
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            for tbl in tables:
                cursor.execute(f"SELECT COUNT(*) AS c FROM {tbl}")
                count = cursor.fetchone()["c"]
                print(f"  {tbl:<22} {count:>8} rows")


def truncate_tables(tables: list[str]) -> None:
    """TRUNCATE semua tabel sekaligus (atomic, cepat)."""
    table_list = ", ".join(tables)
    sql = f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE;"

    print(f"\n>> Running: {sql}")
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute(sql)
    print(">> Done.")


def delete_non_admin_users() -> None:
    """Hapus semua user kecuali yang role='admin'."""
    sql = "DELETE FROM users WHERE role != 'admin';"

    print(f"\n>> Running: {sql}")
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute(sql)
            deleted = cursor.rowcount
    print(f">> Done. {deleted} non-admin user dihapus.")


def main():
    args = set(sys.argv[1:])
    skip_confirm = "--yes" in args or "-y" in args
    full_wipe = "--all" in args

    if full_wipe:
        display_tables = ALL_DISPLAY_TABLES
        truncate_targets = TABLES_TO_WIPE + EXTRA_FULL_WIPE
        mode_label = "FULL WIPE (mentions + keywords + news_sources + non-admin users)"
    else:
        display_tables = TABLES_TO_WIPE
        truncate_targets = TABLES_TO_WIPE
        mode_label = "wipe mentions only"

    print("=" * 50)
    print(" RESET DATABASE - MEDIA MONITORING")
    print("=" * 50)
    print(f"Mode  : {mode_label}")
    print(f"Target: {', '.join(truncate_targets)}")
    if full_wipe:
        print("       + DELETE FROM users WHERE role != 'admin'")
    print("Note  : admin user TIDAK akan dihapus.")

    show_counts("BEFORE", display_tables)

    if not skip_confirm:
        print("\n!! Operasi ini TIDAK BISA DI-UNDO.")
        confirm = input("Ketik 'YES' untuk lanjut: ").strip()
        if confirm != "YES":
            print("Dibatalkan.")
            return

    truncate_tables(truncate_targets)
    if full_wipe:
        delete_non_admin_users()

    show_counts("AFTER", display_tables)

    print("\nSelesai. Tinggal trigger refresh dari admin panel atau:")
    print("   GET http://localhost:8000/refresh-news-test")


if __name__ == "__main__":
    main()
