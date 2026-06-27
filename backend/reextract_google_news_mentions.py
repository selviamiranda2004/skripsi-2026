"""
Re-extract publisher dari title untuk mention yang author='Google News'.

Background: flow ingest lama (tanpa smart fallback) bikin extract_source
return "Google News" untuk title format:
  - "Berita - Google News" (2 segment) — genuinely aggregated, no publisher
  - "Berita - Publisher - Google News" (3+ segment) — publisher real ada di
    tengah, tapi dulu ke-split jadi "Google News" karena ambil last segment

Scripts saat di-INSERT, `mentions.title` disimpan sebagai `title_clean` yang
udah strip " - Google News" dari belakang. Artinya untuk kasus multi-segment,
publisher asli (mis. "Kompas.com") MASIH ADA di `mentions.title`. Kita bisa
re-extract dari sana.

Script ini:
  1. Query mention dengan author ILIKE 'google news'
  2. Re-extract publisher dari mentions.title
  3. Kalau ketemu publisher valid → upsert ke news_sources + update mention
  4. Kalau title gak ada ' - ' → assign ke source 'Unknown'
  5. Cleanup orphan news_sources (row 'Google News' bakal ke-delete kalau
     udah gak ada mention yang nge-point ke dia)

USAGE:
  python reextract_google_news_mentions.py            # interaktif
  python reextract_google_news_mentions.py --yes      # skip konfirmasi
  python reextract_google_news_mentions.py --dry-run  # preview saja
"""

import re
import sys
from collections import Counter
from database import get_db_connection, get_db_cursor


# --------- Helper functions (mirror main.py) ---------

def extract_source(title_raw: str) -> str:
    """Match main.py extract_source dengan smart fallback."""
    if " - " not in title_raw:
        return "Unknown"
    parts = [p.strip() for p in title_raw.split(" - ") if p.strip()]
    if not parts:
        return "Unknown"
    last = parts[-1]
    if last.lower() == "google news" and len(parts) >= 3:
        return parts[-2]
    return last


def slugify(text: str) -> str:
    text = (text or "unknown").lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "unknown"


def guess_publisher_url(name: str, slug: str) -> str:
    domain = slug.replace("-", "")
    return f"https://www.{domain}.com"


def get_or_create_source(cursor, name: str) -> int:
    name = (name or "Unknown").strip()
    slug = slugify(name)
    url = guess_publisher_url(name, slug)
    cursor.execute(
        """
        INSERT INTO news_sources (name, slug, url, category)
        VALUES (%s, %s, %s, 'news')
        ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        (name, slug, url),
    )
    return cursor.fetchone()["id"]


# --------- Main flow ---------

def main():
    skip_confirm = "--yes" in sys.argv or "-y" in sys.argv
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("RE-EXTRACT PUBLISHER dari mention author='Google News'")
    print("=" * 60)

    # Fase 1: fetch semua mention yang author-nya Google News
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute(
                """
                SELECT m.id, m.title, m.source_id, m.author, ns.name AS source_name
                FROM mentions m
                JOIN news_sources ns ON ns.id = m.source_id
                WHERE m.author ILIKE 'google news'
                   OR ns.name ILIKE 'google news'
                ORDER BY m.id
                """
            )
            mentions = [dict(r) for r in cursor.fetchall()]

    if not mentions:
        print("\nTidak ada mention dengan author='Google News'. Udah bersih.")
        return

    print(f"\nTotal mention yang author/source-nya 'Google News': {len(mentions)}")

    # Fase 2: classify by re-extracted publisher
    extracted_counter: Counter = Counter()
    for m in mentions:
        new_pub = extract_source(m["title"] or "")
        # Force "Google News" → "Unknown" (rare edge case, biar final state
        # gak ada author='Google News' tersisa)
        if new_pub.strip().lower() == "google news":
            new_pub = "Unknown"
        extracted_counter[new_pub] += 1

    print("\nPreview re-extraction (top 15 publisher yang bakal di-assign):")
    print(f"  {'Publisher (re-extracted)':<35} {'Count':>8}")
    print("  " + "-" * 45)
    for pub, count in extracted_counter.most_common(15):
        print(f"  {pub:<35} {count:>8}")
    if len(extracted_counter) > 15:
        shown_count = sum(c for _, c in extracted_counter.most_common(15))
        remaining = len(mentions) - shown_count
        print(
            f"  ... dan {len(extracted_counter) - 15} publisher lain "
            f"({remaining} mentions)"
        )

    recoverable = sum(
        c for p, c in extracted_counter.items() if p.lower() != "unknown"
    )
    unknown_count = extracted_counter.get("Unknown", 0)

    print(f"\n  Recoverable (publisher asli ketemu): {recoverable}")
    print(f"  Unknown (title gak punya ' - ')      : {unknown_count}")

    if dry_run:
        print(
            "\n[DRY RUN] Tidak ada perubahan. "
            "Jalankan tanpa --dry-run untuk eksekusi."
        )
        return

    # Fase 3: konfirmasi
    if not skip_confirm:
        print()
        answer = (
            input(
                f"Update {len(mentions)} mention (re-assign source_id + author)? "
                f"(ketik 'yes' untuk lanjut): "
            )
            .strip()
            .lower()
        )
        if answer != "yes":
            print("Dibatalkan.")
            return

    # Fase 4: eksekusi — update per mention
    print(f"\n>> Updating {len(mentions)} mentions...")
    updated = 0
    source_cache: dict[str, int] = {}

    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute("SET statement_timeout = '60s'")

            for m in mentions:
                new_pub = extract_source(m["title"] or "")
                if new_pub.strip().lower() == "google news":
                    new_pub = "Unknown"

                if new_pub not in source_cache:
                    source_cache[new_pub] = get_or_create_source(cursor, new_pub)
                new_source_id = source_cache[new_pub]

                cursor.execute(
                    """
                    UPDATE mentions
                    SET source_id = %s, author = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (new_source_id, new_pub, m["id"]),
                )
                updated += 1

    print(f">> Updated {updated} mentions")

    # Fase 5: cleanup orphan news_sources
    print("\n>> Cleanup orphan news_sources...")
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute(
                """
                DELETE FROM news_sources
                WHERE id NOT IN (SELECT DISTINCT source_id FROM mentions)
                """
            )
            deleted_orphans = cursor.rowcount or 0

            # Stats final
            cursor.execute("SELECT COUNT(*) AS n FROM news_sources")
            total_sources = int(cursor.fetchone()["n"])

            cursor.execute(
                "SELECT COUNT(DISTINCT author) AS n FROM mentions "
                "WHERE author IS NOT NULL AND author <> ''"
            )
            distinct_authors = int(cursor.fetchone()["n"])

            cursor.execute(
                "SELECT COUNT(*) AS n FROM mentions WHERE author ILIKE 'google news'"
            )
            remaining_gn = int(cursor.fetchone()["n"])

    print(f">> Deleted {deleted_orphans} orphan news_sources")
    print("\nFinal state:")
    print(f"  Total news_sources             : {total_sources}")
    print(f"  DISTINCT mentions.author       : {distinct_authors}")
    print(f"  Mentions author='Google News'  : {remaining_gn}")

    if remaining_gn == 0:
        print("\nSelesai. Gak ada lagi mention dengan author='Google News'.")
    else:
        print(
            f"\nAda {remaining_gn} mention yang masih 'Google News'. "
            "Coba jalankan ulang."
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDibatalkan oleh user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
