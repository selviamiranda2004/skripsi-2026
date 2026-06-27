"""
Media Monitoring Dashboard Backend - FastAPI with Authentication
Kementerian UMKM Media Monitoring System
Real-time data dari Google News RSS + simpan ke Supabase
"""

import os
import re
import json
import httpx
import asyncio
import xml.etree.ElementTree as ET
from pathlib import Path
from dotenv import load_dotenv
from collections import Counter
from datetime import datetime, timedelta, timezone, date as date_type

# Timezone WIB (UTC+7) untuk konversi mention_date sesuai zona waktu user
WIB_TZ = timezone(timedelta(hours=7))

# Range valid untuk mention_date (skripsi: data collection window)
# Mention di luar range ini akan di-skip saat ingest.
MENTION_DATE_MIN = date_type(2026, 4, 1)
MENTION_DATE_MAX = date_type(2026, 5, 31)

import fastapi
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import jwt
import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor, Json, execute_values

from database import (
    get_user_by_username,
    get_all_users,
    create_user,
    delete_user,
    update_user,
    update_user_password,
    get_db_connection,
    get_db_cursor,
)

# =========================
# LOAD ENV
# =========================
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

print("✅ DATABASE_URL LOADED:", os.getenv("DATABASE_URL"))

app = FastAPI(title="Media Monitoring API", version="1.0.0")

allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://skripsi-2026.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================================
# MODELS
# ====================================

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str

class CreateUserRequest(BaseModel):
    username: str
    password: str
    email: str = ""
    role: str = "user"

class UpdateUserRequest(BaseModel):
    username: str
    email: str
    role: str

class UserResponse(BaseModel):
    username: str
    role: str

class UpdateSentimentRequest(BaseModel):
    sentiment: str

class VerifyTokenResponse(BaseModel):
    valid: bool
    username: str
    role: str

# ====================================
# KEYWORDS PENCARIAN
# ====================================

SEARCH_KEYWORDS = [
    # === Pejabat & posisi (specific) ===
    "Kementerian UMKM",
    "Maman Abdurrahman",
    "Helvi Moraza",
    "Wakil Menteri UMKM",
    "Deputi UMKM",
    "Menteri UMKM",
    # === Topik umum UMKM (broad — bakal nangkap puluhan/hari) ===
    "UMKM",
    "UMKM Indonesia",
    "pelaku UMKM",
    "pemberdayaan UMKM",
    # === Program & kebijakan UMKM populer ===
    "KUR UMKM",                # Kredit Usaha Rakyat
    "BPUM",                    # Bantuan Produktif Usaha Mikro
    "kredit usaha rakyat",
    "bantuan UMKM",
    # === Tema ekosistem UMKM ===
    "digitalisasi UMKM",
    "ekspor UMKM",
]

# ====================================
# SENTIMENT ANALYSIS (SVM-ONLY)
# ====================================

from sentiment.svm import load_default_model

SVM_MODEL = load_default_model()
if SVM_MODEL is not None:
    print("=" * 60)
    print(" ✅ SENTIMENT MODE: SVM-only")
    print(f"    Model: backend/models/svm_sentiment.joblib")
    print("=" * 60)
else:
    print("=" * 60)
    print(" 🚨 SVM MODEL TIDAK DITEMUKAN")
    print("    Mention baru akan punya sentiment = 'netral' sampai")
    print("    model di-train. Jalankan: python train_sentiment.py")
    print("=" * 60)


def analyze_sentiment_svm(text: str) -> str | None:
    if SVM_MODEL is None or not text:
        return None
    try:
        return SVM_MODEL.predict_one(text)
    except Exception as e:
        print(f"⚠️  SVM predict error: {e}")
        return None


SVM_UNAVAILABLE_DEFAULT = "netral"


def analyze_for_insert(text: str) -> dict:
    svm = analyze_sentiment_svm(text)
    return {
        "sentiment": svm if svm is not None else SVM_UNAVAILABLE_DEFAULT,
        "sentiment_svm": svm,
    }


analyze_both = analyze_for_insert
analyze_sentiment = analyze_for_insert


def compute_svm_details(text: str) -> dict | None:
    if SVM_MODEL is None or not text:
        return None
    try:
        return SVM_MODEL.predict_with_details(text)
    except Exception as e:
        print(f"⚠️  SVM detail predict error: {e}")
        return None


def upsert_sentiment_analysis(cursor, mention_id: int, details: dict | None) -> None:
    if not details or mention_id is None:
        return
    label = details.get("label")
    if not label:
        return
    score_predicted = details.get("score")
    confidence = details.get("confidence")
    payload = {
        "method": "svm",
        "predicted_label": label,
        "scores": details.get("scores", {}),
        "softmax": details.get("softmax", {}),
        "preprocessed_text": details.get("preprocessed_text"),
        "analyzed_at": datetime.utcnow().isoformat() + "Z",
    }
    cursor.execute(
        "DELETE FROM sentiment_analysis WHERE mention_id = %s",
        (mention_id,),
    )
    cursor.execute(
        """
        INSERT INTO sentiment_analysis
            (mention_id, sentiment_score, confidence, analysis_details, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        """,
        (mention_id, score_predicted, confidence, Json(payload)),
    )


def bulk_update_mention_sentiment(
    cursor,
    pairs: list[tuple[int, str]],
) -> int:
    """
    Bulk update kolom sentiment & sentiment_svm di tabel mentions.
    Single query pakai UPDATE FROM VALUES (jauh lebih cepat dari loop UPDATE).
    """
    if not pairs:
        return 0
    execute_values(
        cursor,
        """
        UPDATE mentions AS m
        SET sentiment_svm = data.sent,
            sentiment = data.sent,
            updated_at = NOW()
        FROM (VALUES %s) AS data(id, sent)
        WHERE m.id = data.id
        """,
        pairs,
        template="(%s, %s)",
        page_size=500,
    )
    return len(pairs)


def bulk_upsert_sentiment_analysis(
    cursor,
    mention_ids: list[int],
    details_list: list[dict | None],
) -> int:
    """
    Bulk DELETE + INSERT sentiment_analysis pakai execute_values.
    Single roundtrip per operation (jauh lebih cepat dibanding loop INSERT).
    """
    if not mention_ids:
        return 0
    pairs = [
        (mid, d) for mid, d in zip(mention_ids, details_list)
        if mid is not None and d and d.get("label")
    ]
    if not pairs:
        return 0

    ids_tuple = tuple(p[0] for p in pairs)
    cursor.execute(
        "DELETE FROM sentiment_analysis WHERE mention_id IN %s",
        (ids_tuple,),
    )

    now_iso = datetime.utcnow().isoformat() + "Z"
    rows = []
    for mid, d in pairs:
        payload = {
            "method": "svm",
            "predicted_label": d["label"],
            "scores": d.get("scores", {}),
            "softmax": d.get("softmax", {}),
            "preprocessed_text": d.get("preprocessed_text"),
            "analyzed_at": now_iso,
        }
        rows.append((mid, d.get("score"), d.get("confidence"), Json(payload)))

    # Single INSERT untuk semua rows (execute_values batched ke server)
    execute_values(
        cursor,
        """
        INSERT INTO sentiment_analysis
            (mention_id, sentiment_score, confidence, analysis_details, created_at)
        VALUES %s
        """,
        rows,
        template="(%s, %s, %s, %s, NOW())",
        page_size=500,
    )
    return len(rows)


# ====================================
# GOOGLE NEWS RSS FETCHER
# ====================================

def parse_rss_datetime(date_str: str):
    if not date_str or not date_str.strip():
        return None
    try:
        from email.utils import parsedate_to_datetime
        from datetime import timezone
        dt = parsedate_to_datetime(date_str.strip())
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def parse_rss_date(date_str: str) -> str:
    dt = parse_rss_datetime(date_str)
    if dt is None:
        dt = datetime.utcnow()
    return dt.strftime("%Y-%m-%d")


# ====================================
# REFRESH STATE TRACKING (incremental fetch)
# ====================================
# Simpan timestamp refresh terakhir agar sistem hanya mengambil mention baru
# (pubDate >= last_refresh_at) pada refresh berikutnya.
_REFRESH_STATE_FILE = BASE_DIR / "data" / "refresh_state.json"


def get_last_refresh_at() -> datetime | None:
    """Baca timestamp refresh terakhir (UTC naive). None = belum pernah refresh."""
    try:
        if not _REFRESH_STATE_FILE.exists():
            return None
        data = json.loads(_REFRESH_STATE_FILE.read_text(encoding="utf-8"))
        ts = data.get("last_refresh_at")
        if not ts:
            return None
        return datetime.fromisoformat(ts)
    except Exception as e:
        print(f"⚠️  gagal baca refresh state: {e}")
        return None


def set_last_refresh_at(dt: datetime) -> None:
    """Simpan timestamp refresh terakhir (UTC naive) ke file state."""
    try:
        _REFRESH_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _REFRESH_STATE_FILE.write_text(
            json.dumps({"last_refresh_at": dt.isoformat()}),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"⚠️  gagal simpan refresh state: {e}")


def extract_source(title_raw: str) -> str:
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


_DOMAIN_IN_NAME_RE = re.compile(
    r"([a-z0-9][\w-]*\.(?:com|co\.id|co|net|id|tv|news|org))",
    re.IGNORECASE,
)

PUBLISHER_URL_OVERRIDES: dict[str, str] = {
    "republika online":      "https://www.republika.co.id",
    "antara":                "https://www.antaranews.com",
    "antara news":           "https://www.antaranews.com",
    "metrotv news":          "https://www.metrotvnews.com",
    "metro tv news":         "https://www.metrotvnews.com",
    "tribunnews":            "https://www.tribunnews.com",
    "tribun news":           "https://www.tribunnews.com",
    "kompas":                "https://www.kompas.com",
    "detik":                 "https://www.detik.com",
    "tempo":                 "https://www.tempo.co",
    "cnn indonesia":         "https://www.cnnindonesia.com",
    "cnbc indonesia":        "https://www.cnbcindonesia.com",
    "bbc news indonesia":    "https://www.bbc.com/indonesia",
    "voi.id":                "https://voi.id",
    "katadata":              "https://katadata.co.id",
    "jawa pos":              "https://www.jawapos.com",
    "media indonesia":       "https://mediaindonesia.com",
}


def guess_publisher_url(name: str, slug: str) -> str:
    name_clean = (name or "").strip().lower()
    if name_clean in PUBLISHER_URL_OVERRIDES:
        return PUBLISHER_URL_OVERRIDES[name_clean]
    match = _DOMAIN_IN_NAME_RE.search(name_clean)
    if match:
        return f"https://www.{match.group(1).lower()}"
    domain = slug.replace("-", "")
    return f"https://www.{domain}.com"


def get_or_create_source(cursor, name: str, source_url: str | None = None) -> int:
    name = (name or "Unknown").strip()
    slug = slugify(name)
    source_url_clean = (source_url or "").strip()
    if source_url_clean:
        cursor.execute(
            """
            INSERT INTO news_sources (name, slug, url, category)
            VALUES (%s, %s, %s, 'news')
            ON CONFLICT (slug) DO UPDATE SET
                name = EXCLUDED.name,
                url  = EXCLUDED.url
            RETURNING id
            """,
            (name, slug, source_url_clean),
        )
    else:
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


async def resolve_google_news_url(client: httpx.AsyncClient, url: str) -> str:
    """Follow redirect Google News URL ke URL artikel asli."""
    try:
        res = await client.head(url, follow_redirects=True, timeout=10.0)
        return str(res.url)
    except Exception:
        return url


async def fetch_rss_single(
    client: httpx.AsyncClient,
    query: str,
    after_date: date_type | None = None,
    before_date: date_type | None = None,
) -> tuple:
    """
    Fetch Google News RSS untuk 1 keyword.
    Optional: pakai Google News date operator (after:/before:) untuk historical backfill.
    """
    encoded_query = query.replace(" ", "+")
    date_ops = []
    if after_date:
        date_ops.append(f"after:{after_date.isoformat()}")
    if before_date:
        date_ops.append(f"before:{before_date.isoformat()}")
    full_query = encoded_query
    if date_ops:
        full_query = encoded_query + "+" + "+".join(date_ops)
    url = f"https://news.google.com/rss/search?q={full_query}&hl=id&gl=ID&ceid=ID:id"
    for attempt in range(3):
        try:
            response = await client.get(url)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            channel = root.find("channel")
            if channel is None:
                return (query, [])
            return (query, channel.findall("item"))
        except Exception as e:
            print(f"⚠️ Attempt {attempt+1} gagal untuk '{query}': {e}")
            if attempt < 2:
                await asyncio.sleep(2)
    print(f"❌ Skip '{query}' setelah 3x gagal")
    return (query, [])


_DB_DEAD_ERRORS = (psycopg2.InterfaceError, psycopg2.OperationalError)


async def fetch_and_save_all_news(force: bool = False) -> dict:
    import time
    t0 = time.time()

    # =========================
    # FILTER POLICY
    # =========================
    # 1. Range valid: hanya ingest mention dalam window MENTION_DATE_MIN..MAX.
    # 2. Last-24h (default): hanya ingest artikel yang dipublish dalam
    #    24 jam terakhir (rolling window dari sekarang WIB).
    # 3. force=True: skip filter last-24h (tapi range tetap berlaku).
    session_started_at = datetime.utcnow()
    now_wib = datetime.now(WIB_TZ)
    today_wib = now_wib.date()
    cutoff_dt_wib = now_wib - timedelta(hours=24)

    if force:
        mode_label = "force (semua tanggal dalam range)"
    else:
        mode_label = f"last-24h (sejak {cutoff_dt_wib.strftime('%Y-%m-%d %H:%M')} WIB)"

    print(
        f"\n🔄 [refresh] fetching {len(SEARCH_KEYWORDS)} keywords — mode: {mode_label}"
    )
    print(
        f"    range valid: {MENTION_DATE_MIN.isoformat()} s/d {MENTION_DATE_MAX.isoformat()}"
    )

    # Early exit kalau hari ini di luar range valid
    if not (MENTION_DATE_MIN <= today_wib <= MENTION_DATE_MAX) and not force:
        print(
            f"⚠️  [refresh] hari ini ({today_wib}) di luar range valid, "
            f"tidak ada mention yang akan diingest."
        )
        return {
            "total": 0,
            "detail": {},
            "skipped_too_old": 0,
            "skipped_out_of_range": 0,
            "mode": "last-24h",
            "cutoff_wib": cutoff_dt_wib.isoformat(),
            "range": [MENTION_DATE_MIN.isoformat(), MENTION_DATE_MAX.isoformat()],
            "warning": "Hari ini di luar range valid (1 Jan - 31 Mei 2026).",
        }

    results: dict = {}
    total = 0
    skipped_too_old = 0        # pubDate < cutoff (24 jam lalu)
    skipped_out_of_range = 0   # pubDate di luar MIN..MAX
    any_connection_died = False

    # =========================
    # 1. FETCH RSS + RESOLVE URL PARALEL
    # =========================
    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
        ) as client:
            # Fetch RSS semua keyword paralel
            tasks = [
                fetch_rss_single(
                    client, kw,
                    after_date=MENTION_DATE_MIN,
                    before_date=MENTION_DATE_MAX,
                    )
                     for kw in SEARCH_KEYWORDS
                     ]
            all_results = await asyncio.gather(*tasks)

            # Kumpulkan semua URL unik untuk di-resolve paralel
            print("🔗 [refresh] resolving redirect URLs...")
            resolved_map: dict[str, str] = {}
            resolve_tasks = []
            raw_urls = []

            for _, items in all_results:
                for item in items:
                    raw_link = (item.findtext("link") or "")[:300]
                    if raw_link and raw_link not in resolved_map:
                        resolve_tasks.append(
                            resolve_google_news_url(client, raw_link)
                        )
                        raw_urls.append(raw_link)

            if resolve_tasks:
                resolved_results = await asyncio.gather(*resolve_tasks)
                for raw, resolved in zip(raw_urls, resolved_results):
                    resolved_map[raw] = resolved[:300]

            resolve_dur = time.time() - t0
            print(f"🔗 [refresh] resolved {len(resolved_map)} URLs in {resolve_dur:.1f}s")

    except Exception as e:
        print(f"🔥 RSS FETCH ERROR: {e}")
        raise HTTPException(502, f"Gagal fetch Google News RSS: {e}")

    fetched_count = sum(len(items) for _, items in all_results)
    print(f"📥 [refresh] RSS fetched {fetched_count} items")

    if fetched_count == 0:
        return {"total": 0, "detail": {}, "warning": "RSS kosong, mungkin Google News blok request"}

    # =========================
    # 2. AMBIL keywords_map (sync SEARCH_KEYWORDS dulu biar keyword baru auto-create)
    # =========================
    try:
        ensure_keywords_in_db()
        keywords_map = get_keywords_map()
    except Exception as e:
        print(f"⚠️  gagal load keywords map: {e}, lanjut tanpa relasi keyword")
        keywords_map = {}
    if not keywords_map:
        print("⚠️  Tabel keywords kosong, mention tetap masuk tapi tanpa relasi")

    # =========================
    # 3. INSERT PER KEYWORD
    # =========================
    for keyword, items in all_results:
        saved = 0
        keyword_id = keywords_map.get(keyword)
        source_cache: dict[str, int] = {}
        connection_died = False

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                try:
                    cursor.execute("SET statement_timeout = '30s'")

                    def cached_source_id(publisher: str, publisher_url: str | None = None) -> int:
                        if publisher not in source_cache:
                            source_cache[publisher] = get_or_create_source(
                                cursor, publisher, publisher_url
                            )
                        return source_cache[publisher]

                    # PRE-FILTER: bulk check URL yang sudah ada
                    candidate_urls: list[str] = []
                    for it in items:
                        raw_link = (it.findtext("link") or "")[:300]
                        resolved_link = resolved_map.get(raw_link, raw_link)
                        if resolved_link:
                            candidate_urls.append(resolved_link)

                    existing_urls: set[str] = set()
                    if candidate_urls:
                        cursor.execute(
                            "SELECT url FROM mentions WHERE url = ANY(%s)",
                            (candidate_urls,),
                        )
                        existing_urls = {r["url"] for r in cursor.fetchall()}
                        if existing_urls:
                            print(
                                f"⏭️  [refresh] '{keyword}': skip {len(existing_urls)}"
                                f"/{len(candidate_urls)} duplicate URLs"
                            )

                    for item in items:
                        if connection_died:
                            break

                        try:
                            title_raw = (item.findtext("title") or "").strip()
                            raw_link = (item.findtext("link") or "")[:300]
                            pub = item.findtext("pubDate") or ""

                            # Pakai resolved URL (URL artikel asli)
                            link = resolved_map.get(raw_link, raw_link)[:300]
                            
                            source_el = item.find("source")
                            publisher_url = (
                                (source_el.get("url") or "").strip()
                                if source_el is not None
                                else ""
                            )

                            if not title_raw or not link:
                                continue

                            if link in existing_urls:
                                continue

                            mention_dt = parse_rss_datetime(pub)
                            if mention_dt is None:
                                mention_dt = datetime.utcnow()

                            # Konversi UTC naive → WIB untuk mendapatkan waktu
                            # yang benar sesuai zona waktu Indonesia.
                            mention_dt_wib = mention_dt.replace(tzinfo=timezone.utc).astimezone(WIB_TZ)
                            mention_date_wib = mention_dt_wib.date()

                            # FILTER 1: range valid (1 Jan - 31 Mei 2026)
                            if not (MENTION_DATE_MIN <= mention_date_wib <= MENTION_DATE_MAX):
                                skipped_out_of_range += 1
                                continue

                            # FILTER 2: last-24h window (kecuali force=True)
                            if not force and mention_dt_wib < cutoff_dt_wib:
                                skipped_too_old += 1
                                continue

                            publisher = extract_source(title_raw)
                            title_clean = re.sub(r"\s*-\s*[^-]+$", "", title_raw).strip() or title_raw
                            source_id = cached_source_id(publisher, publisher_url)
                            date = mention_date_wib.strftime("%Y-%m-%d")

                            svm_details = compute_svm_details(title_clean)
                            sentiment_label = (svm_details or {}).get("label") or SVM_UNAVAILABLE_DEFAULT
                            svm_label = (svm_details or {}).get("label")

                            cursor.execute("SAVEPOINT sp_row")
                            try:
                                cursor.execute(
                                    """
                                    INSERT INTO mentions
                                    (title, content, source_id, author, url,
                                     sentiment, sentiment_svm,
                                     mention_date, created_at, updated_at)
                                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
                                    ON CONFLICT (url) DO NOTHING
                                    RETURNING id
                                    """,
                                    (
                                        title_clean, title_clean, source_id, publisher, link,
                                        sentiment_label, svm_label, date,
                                    ),
                                )
                                row = cursor.fetchone()
                                if row:
                                    mention_id = row["id"]
                                    saved += 1
                                    if keyword_id:
                                        cursor.execute(
                                            """
                                            INSERT INTO mention_keywords (mention_id, keyword_id)
                                            VALUES (%s,%s)
                                            ON CONFLICT DO NOTHING
                                            """,
                                            (mention_id, keyword_id),
                                        )
                                    if svm_details:
                                        payload = {
                                            "method": "svm",
                                            "predicted_label": svm_label,
                                            "scores": svm_details.get("scores", {}),
                                            "softmax": svm_details.get("softmax", {}),
                                            "preprocessed_text": svm_details.get("preprocessed_text"),
                                            "analyzed_at": datetime.utcnow().isoformat() + "Z",
                                        }
                                        cursor.execute(
                                            """
                                            INSERT INTO sentiment_analysis
                                                (mention_id, sentiment_score, confidence,
                                                 analysis_details, created_at)
                                            VALUES (%s, %s, %s, %s, NOW())
                                            """,
                                            (
                                                mention_id,
                                                svm_details.get("score"),
                                                svm_details.get("confidence"),
                                                Json(payload),
                                            ),
                                        )
                                cursor.execute("RELEASE SAVEPOINT sp_row")
                            except _DB_DEAD_ERRORS:
                                raise
                            except Exception as row_e:
                                print(f"❌ row error '{keyword}': {row_e}")
                                try:
                                    cursor.execute("ROLLBACK TO SAVEPOINT sp_row")
                                except _DB_DEAD_ERRORS:
                                    raise

                        except _DB_DEAD_ERRORS as conn_e:
                            print(f"💀 [refresh] connection dropped saat '{keyword}' (saved={saved}): {conn_e}")
                            connection_died = True
                            break

                finally:
                    try:
                        cursor.close()
                    except Exception:
                        pass
                    if connection_died:
                        try:
                            conn.close()
                        except Exception:
                            pass

        except _DB_DEAD_ERRORS as e:
            print(f"💀 [refresh] connection error final saat '{keyword}': {e}")
            any_connection_died = True
        except Exception as e:
            print(f"🔥 [refresh] unexpected error saat '{keyword}': {e}")

        if connection_died:
            any_connection_died = True

        results[keyword] = saved
        total += saved

    total_dur = time.time() - t0
    print(
        f"✅ [refresh] saved {total} new mentions, "
        f"skipped {skipped_too_old} (>24h old), "
        f"skipped {skipped_out_of_range} (out of range) in {total_dur:.1f}s"
    )
    print(f"    detail: {results}")

    # Update last_refresh_at sekedar untuk info (tidak dipakai filter lagi)
    if not any_connection_died:
        set_last_refresh_at(session_started_at)

    return {
        "total": total,
        "detail": results,
        "skipped_too_old": skipped_too_old,
        "skipped_out_of_range": skipped_out_of_range,
        "mode": "force" if force else "last-24h",
        "cutoff_wib": cutoff_dt_wib.isoformat(),
        "range": [MENTION_DATE_MIN.isoformat(), MENTION_DATE_MAX.isoformat()],
        "last_refresh_at": session_started_at.isoformat() + "Z",
    }


# ====================================
# HISTORICAL BACKFILL
# ====================================
async def fetch_and_save_historical(
    start_date: date_type,
    end_date: date_type,
    chunk_days: int = 7,
) -> dict:
    """
    Backfill mention historis dengan Google News date operator (after:/before:).
    Iterasi range [start_date, end_date] per chunk_days hari.
    """
    import time as _time

    # Clamp ke range valid
    effective_start = max(start_date, MENTION_DATE_MIN)
    effective_end = min(end_date, MENTION_DATE_MAX)
    if effective_start > effective_end:
        return {
            "error": "Range di luar window valid",
            "chunks_processed": 0,
            "total_saved": 0,
        }

    # Generate chunks
    chunks: list[tuple[date_type, date_type]] = []
    cur = effective_start
    while cur <= effective_end:
        chunk_end = min(cur + timedelta(days=chunk_days - 1), effective_end)
        chunks.append((cur, chunk_end))
        cur = chunk_end + timedelta(days=1)

    print(
        f"\n🗓️  [backfill] {len(chunks)} chunks × {len(SEARCH_KEYWORDS)} keywords — "
        f"{effective_start.isoformat()} s/d {effective_end.isoformat()}"
    )

    t0 = _time.time()
    total_saved = 0
    total_skipped_dup = 0
    total_skipped_oor = 0
    errors: list[str] = []

    try:
        ensure_keywords_in_db()
        keywords_map = get_keywords_map()
    except Exception:
        keywords_map = {}

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for chunk_idx, (c_start, c_end) in enumerate(chunks, 1):
            chunk_label = f"{c_start.isoformat()} → {c_end.isoformat()}"
            print(f"\n  📅 chunk {chunk_idx}/{len(chunks)}: {chunk_label}")

            # Fetch RSS semua keyword untuk chunk ini (paralel)
            # before: di Google News bersifat exclusive, jadi +1 hari
            tasks = [
                fetch_rss_single(
                    client, kw,
                    after_date=c_start,
                    before_date=c_end + timedelta(days=1),
                )
                for kw in SEARCH_KEYWORDS
            ]
            try:
                chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                errors.append(f"{chunk_label}: gather error: {e}")
                continue

            # Kumpulkan items + URL unik buat resolve
            all_items_kw: list[tuple[str, any]] = []
            raw_urls: set[str] = set()
            for kr in chunk_results:
                if isinstance(kr, Exception):
                    errors.append(f"{chunk_label}: fetch: {kr}")
                    continue
                keyword, items = kr
                for item in items:
                    raw_link = (item.findtext("link") or "")[:300]
                    if raw_link:
                        raw_urls.add(raw_link)
                    all_items_kw.append((keyword, item))

            if not all_items_kw:
                print(f"     (tidak ada item)")
                await asyncio.sleep(1.0)
                continue

            # Resolve URLs paralel
            resolved_map: dict[str, str] = {}
            if raw_urls:
                resolve_tasks = [resolve_google_news_url(client, u) for u in raw_urls]
                resolved_results = await asyncio.gather(*resolve_tasks, return_exceptions=True)
                for raw, resolved in zip(raw_urls, resolved_results):
                    if isinstance(resolved, Exception):
                        resolved_map[raw] = raw
                    else:
                        resolved_map[raw] = resolved[:300]

            # Insert ke DB
            chunk_saved = 0
            chunk_dup = 0
            chunk_oor = 0
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor(cursor_factory=RealDictCursor)
                    try:
                        cursor.execute("SET statement_timeout = '60s'")
                        source_cache: dict[str, int] = {}

                        # Pre-check URL duplikat
                        candidate_urls = list({resolved_map.get(
                            (it.findtext("link") or "")[:300],
                            (it.findtext("link") or "")[:300],
                        )[:300] for _, it in all_items_kw})
                        existing_urls: set[str] = set()
                        if candidate_urls:
                            cursor.execute(
                                "SELECT url FROM mentions WHERE url = ANY(%s)",
                                (candidate_urls,),
                            )
                            existing_urls = {r["url"] for r in cursor.fetchall()}

                        for keyword, item in all_items_kw:
                            try:
                                title_raw = (item.findtext("title") or "").strip()
                                raw_link = (item.findtext("link") or "")[:300]
                                pub = item.findtext("pubDate") or ""
                                link = resolved_map.get(raw_link, raw_link)[:300]

                                if not title_raw or not link:
                                    continue
                                if link in existing_urls:
                                    chunk_dup += 1
                                    continue

                                mention_dt = parse_rss_datetime(pub)
                                if mention_dt is None:
                                    continue  # Backfill wajib ada tanggal valid

                                mention_dt_wib = mention_dt.replace(tzinfo=timezone.utc).astimezone(WIB_TZ)
                                mention_date_wib = mention_dt_wib.date()

                                # Filter: harus dalam range GLOBAL
                                if not (MENTION_DATE_MIN <= mention_date_wib <= MENTION_DATE_MAX):
                                    chunk_oor += 1
                                    continue
                                # Filter: harus dalam chunk range (safety, Google kadang nyimpang)
                                if not (c_start <= mention_date_wib <= c_end):
                                    chunk_oor += 1
                                    continue

                                source_el = item.find("source")
                                publisher_url = (
                                    (source_el.get("url") or "").strip()
                                    if source_el is not None else ""
                                )
                                publisher = extract_source(title_raw)
                                title_clean = re.sub(r"\s*-\s*[^-]+$", "", title_raw).strip() or title_raw
                                if publisher not in source_cache:
                                    source_cache[publisher] = get_or_create_source(cursor, publisher, publisher_url)
                                source_id = source_cache[publisher]
                                date = mention_date_wib.strftime("%Y-%m-%d")

                                svm_details = compute_svm_details(title_clean)
                                sentiment_label = (svm_details or {}).get("label") or SVM_UNAVAILABLE_DEFAULT
                                svm_label = (svm_details or {}).get("label")

                                cursor.execute("SAVEPOINT sp_row")
                                try:
                                    cursor.execute(
                                        """
                                        INSERT INTO mentions
                                        (title, content, source_id, author, url,
                                         sentiment, sentiment_svm,
                                         mention_date, created_at, updated_at)
                                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
                                        ON CONFLICT (url) DO NOTHING
                                        RETURNING id
                                        """,
                                        (
                                            title_clean, title_clean, source_id, publisher, link,
                                            sentiment_label, svm_label, date,
                                        ),
                                    )
                                    row = cursor.fetchone()
                                    if row:
                                        mention_id = row["id"]
                                        chunk_saved += 1
                                        keyword_id = keywords_map.get(keyword)
                                        if keyword_id:
                                            cursor.execute(
                                                """
                                                INSERT INTO mention_keywords (mention_id, keyword_id)
                                                VALUES (%s,%s) ON CONFLICT DO NOTHING
                                                """,
                                                (mention_id, keyword_id),
                                            )
                                        if svm_details:
                                            payload = {
                                                "method": "svm",
                                                "predicted_label": svm_label,
                                                "scores": svm_details.get("scores", {}),
                                                "softmax": svm_details.get("softmax", {}),
                                                "preprocessed_text": svm_details.get("preprocessed_text"),
                                                "analyzed_at": datetime.utcnow().isoformat() + "Z",
                                            }
                                            cursor.execute(
                                                """
                                                INSERT INTO sentiment_analysis
                                                    (mention_id, sentiment_score, confidence,
                                                     analysis_details, created_at)
                                                VALUES (%s, %s, %s, %s, NOW())
                                                """,
                                                (
                                                    mention_id,
                                                    svm_details.get("score"),
                                                    svm_details.get("confidence"),
                                                    Json(payload),
                                                ),
                                            )
                                    cursor.execute("RELEASE SAVEPOINT sp_row")
                                except _DB_DEAD_ERRORS:
                                    raise
                                except Exception as row_e:
                                    try:
                                        cursor.execute("ROLLBACK TO SAVEPOINT sp_row")
                                    except _DB_DEAD_ERRORS:
                                        raise
                                    errors.append(f"{chunk_label}: row: {row_e}")
                            except _DB_DEAD_ERRORS as conn_e:
                                errors.append(f"{chunk_label}: conn drop: {conn_e}")
                                break
                            except Exception as item_e:
                                errors.append(f"{chunk_label}: item: {item_e}")
                    finally:
                        try:
                            cursor.close()
                        except Exception:
                            pass
            except Exception as conn_e:
                errors.append(f"{chunk_label}: DB: {conn_e}")

            total_saved += chunk_saved
            total_skipped_dup += chunk_dup
            total_skipped_oor += chunk_oor
            print(
                f"     ✓ saved {chunk_saved}, duplicate {chunk_dup}, "
                f"out-of-range {chunk_oor}"
            )

            # Rate limit: jeda antar chunk supaya Google nggak block
            await asyncio.sleep(1.5)

    dur = _time.time() - t0
    print(
        f"\n🎉 [backfill] selesai. Total saved: {total_saved}, "
        f"dup: {total_skipped_dup}, oor: {total_skipped_oor} in {dur:.1f}s"
    )

    return {
        "chunks_processed": len(chunks),
        "chunk_days": chunk_days,
        "total_saved": total_saved,
        "total_skipped_duplicate": total_skipped_dup,
        "total_skipped_out_of_range": total_skipped_oor,
        "errors": errors[:20],
        "range": [effective_start.isoformat(), effective_end.isoformat()],
        "duration_seconds": round(dur, 1),
    }


# ====================================
# AUTH HELPERS
# ====================================
def get_keywords_map():
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute("SELECT id, keyword FROM keywords WHERE is_active = true")
            rows = cursor.fetchall()
            return {row["keyword"]: row["id"] for row in rows}


def ensure_keywords_in_db():
    """
    Pastikan semua entry di SEARCH_KEYWORDS ada di tabel `keywords`.
    Dipanggil saat startup + sebelum refresh, supaya keyword baru yang
    ditambah ke SEARCH_KEYWORDS otomatis terbentuk relasinya di mention_keywords.
    """
    if not SEARCH_KEYWORDS:
        return
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                rows = [(kw,) for kw in SEARCH_KEYWORDS]
                execute_values(
                    cursor,
                    """
                    INSERT INTO keywords (keyword, is_active, created_at)
                    VALUES %s
                    ON CONFLICT (keyword) DO UPDATE
                    SET is_active = true
                    """,
                    rows,
                    template="(%s, true, NOW())",
                )
                print(f"✅ keywords synced: {len(SEARCH_KEYWORDS)} keyword(s) aktif di DB")
    except Exception as e:
        print(f"⚠️  ensure_keywords_in_db gagal: {e}")


@app.on_event("startup")
async def _startup_sync_keywords():
    """Sync SEARCH_KEYWORDS ke DB tiap kali backend boot."""
    ensure_keywords_in_db()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def create_access_token(username: str, role: str) -> str:
    payload = {
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None

def get_current_user(authorization: str = fastapi.Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        token = authorization.split(" ")[1]
    except IndexError:
        raise HTTPException(status_code=401, detail="Invalid token format")
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

def get_admin_user(authorization: str = fastapi.Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        token = authorization.split(" ")[1]
    except IndexError:
        raise HTTPException(status_code=401, detail="Invalid token format")
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload

def get_mentions_from_db(start_date: str | None = None, end_date: str | None = None) -> list:
    where_parts = []
    params: list = []
    if start_date:
        where_parts.append("mention_date >= %s::date")
        params.append(start_date)
    if end_date:
        where_parts.append("mention_date < (%s::date + INTERVAL '1 day')")
        params.append(end_date)
    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    sql = f"""
        SELECT
            id, title, content, author, url, sentiment,
            TO_CHAR(mention_date, 'YYYY-MM-DD') AS date,
            'online' AS source
        FROM mentions
        {where_sql}
        ORDER BY mention_date DESC, created_at DESC
    """
    with get_db_cursor() as cursor:
        cursor.execute(sql, params)
        results = cursor.fetchall()
        return [dict(row) for row in results] if results else []


# ====================================
# AUTH ENDPOINTS
# ====================================

@app.post("/auth/login")
async def login(request: LoginRequest):
    user = get_user_by_username(request.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user["username"], user["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user["username"],
        "role": user["role"]
    }

@app.post("/auth/verify", response_model=VerifyTokenResponse)
async def verify(authorization: str = fastapi.Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        token = authorization.split(" ")[1]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token format")
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return VerifyTokenResponse(
        valid=True,
        username=payload.get("username"),
        role=payload.get("role")
    )

@app.get("/reset-admin")
async def reset_admin():
    password_hash = hash_password("admin123")
    update_user_password(1, password_hash)
    return {"message": "admin password reset to admin123"}


# ====================================
# USER ENDPOINTS
# ====================================

@app.post("/auth/create-user")
async def create_user_endpoint(
    request: CreateUserRequest,
    current_user=Depends(get_admin_user)
):
    try:
        password_hash = hash_password(request.password)
        user = create_user(
            username=request.username,
            email=request.email,
            password_hash=password_hash,
            role=request.role
        )
        return UserResponse(username=user['username'], role=user['role'])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/auth/users")
async def get_users(admin=Depends(get_admin_user)):
    users = get_all_users()
    return {
        "users": [
            {
                "username": u["username"],
                "role": u["role"],
                "email": u.get("email", "")
            }
            for u in users
        ]
    }

@app.put("/auth/users/{username}")
async def update_user_endpoint(
    username: str,
    request: UpdateUserRequest,
    admin=Depends(get_admin_user),
):
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    updated = update_user(user["id"], {
        "username": request.username,
        "email": request.email,
        "role": request.role,
    })
    if not updated:
        raise HTTPException(status_code=500, detail="Gagal mengupdate user")
    return {"message": "User updated successfully", "user": updated}

@app.delete("/auth/users/{username}")
async def delete_user_endpoint(
    username: str,
    admin=Depends(get_admin_user)
):
    if username == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete admin")
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    delete_user(user["id"])
    return {"message": f"{username} deleted"}


# ====================================
# API ENDPOINTS
# ====================================

@app.get("/health")
async def health():
    return {"status": "ok", "message": "Media Monitoring API is running"}

@app.get("/refresh-news-test")
async def refresh_news_test(force: bool = False):
    result = await fetch_and_save_all_news(force=force)
    return {"message": "News refreshed", **result}

@app.post("/refresh-news")
async def refresh_news(force: bool = False, current_user=Depends(get_current_user)):
    """
    Refresh news dari Google News RSS.

    Policy:
    - Range valid: 1 Januari 2026 s/d 31 Mei 2026 (mention di luar range di-skip)
    - Default (force=False): LAST-24H — hanya ingest artikel yang dipublish dalam
      24 jam terakhir (rolling window dari sekarang WIB). Artikel yang lebih
      lama otomatis di-skip meski URL-nya baru.
    - force=True: ingest semua artikel dalam range yang tersedia di RSS feed
      (~7 hari ke belakang). Untuk backfill manual / debugging.
    """
    result = await fetch_and_save_all_news(force=force)
    return {"message": "News refreshed", **result}


@app.get("/refresh-state")
async def get_refresh_state(current_user=Depends(get_current_user)):
    """Lihat timestamp refresh terakhir."""
    last = get_last_refresh_at()
    return {
        "last_refresh_at": last.isoformat() + "Z" if last else None,
        "has_state": last is not None,
    }


@app.delete("/refresh-state")
async def reset_refresh_state(current_user=Depends(get_admin_user)):
    """Reset state refresh — refresh berikutnya akan jadi full fetch."""
    try:
        if _REFRESH_STATE_FILE.exists():
            _REFRESH_STATE_FILE.unlink()
        return {"message": "Refresh state direset. Refresh berikutnya = full fetch."}
    except Exception as e:
        raise HTTPException(500, f"Gagal reset state: {e}")


@app.get("/admin/mentions-out-of-range")
async def count_mentions_out_of_range(admin=Depends(get_admin_user)):
    """Hitung mention di luar range valid (Jan 1 - Mei 31 2026)."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_out_of_range,
                COUNT(*) FILTER (WHERE mention_date < %s) AS before_range,
                COUNT(*) FILTER (WHERE mention_date > %s) AS after_range,
                MIN(mention_date) AS oldest,
                MAX(mention_date) AS newest
            FROM mentions
            WHERE mention_date < %s OR mention_date > %s
            """,
            (
                MENTION_DATE_MIN, MENTION_DATE_MAX,
                MENTION_DATE_MIN, MENTION_DATE_MAX,
            ),
        )
        row = cursor.fetchone()
    return {
        "range": [MENTION_DATE_MIN.isoformat(), MENTION_DATE_MAX.isoformat()],
        "total_out_of_range": row["total_out_of_range"] if row else 0,
        "before_range": row["before_range"] if row else 0,
        "after_range": row["after_range"] if row else 0,
        "oldest": row["oldest"].isoformat() if row and row["oldest"] else None,
        "newest": row["newest"].isoformat() if row and row["newest"] else None,
    }


@app.post("/admin/backfill-historical")
async def backfill_historical(
    start_date: str,
    end_date: str,
    chunk_days: int = 7,
    admin=Depends(get_admin_user),
):
    """
    Backfill mention historis dari Google News dengan date operator.

    Query params:
    - start_date: ISO format YYYY-MM-DD (e.g. 2026-01-01)
    - end_date: ISO format YYYY-MM-DD (e.g. 2026-05-31)
    - chunk_days: ukuran window per chunk (default 7 hari)

    Catatan:
    - Iterasi per chunk_days hari, pakai Google News 'after:'/'before:' operator.
    - Jeda 1.5 detik antar chunk supaya Google tidak rate-limit.
    - Range di-clamp ke MENTION_DATE_MIN..MAX (1 Jan - 31 Mei 2026).
    - Hasil bisa lebih sedikit dari ekspektasi: Google News archive
      kadang tidak lengkap untuk tanggal lama.
    """
    try:
        sd = date_type.fromisoformat(start_date)
        ed = date_type.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(400, "Format tanggal harus YYYY-MM-DD")

    if sd > ed:
        raise HTTPException(400, "start_date harus <= end_date")
    if chunk_days < 1 or chunk_days > 30:
        raise HTTPException(400, "chunk_days harus 1-30")

    result = await fetch_and_save_historical(sd, ed, chunk_days=chunk_days)
    return {"message": "Historical backfill selesai", **result}


@app.delete("/admin/mentions-out-of-range")
async def delete_mentions_out_of_range(admin=Depends(get_admin_user)):
    """
    Hapus semua mention di luar range valid (Jan 1 - Mei 31 2026).
    Termasuk sentiment_analysis dan mention_keywords yang terkait.
    """
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute("SET statement_timeout = '60s'")

            # Ambil ID yang akan dihapus
            cursor.execute(
                """
                SELECT id FROM mentions
                WHERE mention_date < %s OR mention_date > %s
                """,
                (MENTION_DATE_MIN, MENTION_DATE_MAX),
            )
            ids = [r["id"] for r in cursor.fetchall()]

            if not ids:
                return {
                    "message": "Tidak ada mention di luar range.",
                    "deleted": 0,
                }

            # Hapus child tables dulu, lalu mentions
            cursor.execute(
                "DELETE FROM sentiment_analysis WHERE mention_id = ANY(%s)",
                (ids,),
            )
            sa_deleted = cursor.rowcount

            cursor.execute(
                "DELETE FROM mention_keywords WHERE mention_id = ANY(%s)",
                (ids,),
            )
            mk_deleted = cursor.rowcount

            cursor.execute(
                "DELETE FROM mentions WHERE id = ANY(%s)",
                (ids,),
            )
            m_deleted = cursor.rowcount

    return {
        "message": "Cleanup selesai.",
        "deleted_mentions": m_deleted,
        "deleted_sentiment_analysis": sa_deleted,
        "deleted_mention_keywords": mk_deleted,
        "range": [MENTION_DATE_MIN.isoformat(), MENTION_DATE_MAX.isoformat()],
    }

@app.post("/admin/cleanup-orphan-sources")
async def cleanup_orphan_sources(admin=Depends(get_admin_user)):
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                cursor.execute("SET statement_timeout = '30s'")
                cursor.execute(
                    """
                    SELECT id, name, slug FROM news_sources
                    WHERE id NOT IN (SELECT DISTINCT source_id FROM mentions)
                    ORDER BY name
                    """
                )
                orphans = [dict(r) for r in cursor.fetchall()]
                if not orphans:
                    cursor.execute("SELECT COUNT(*) AS n FROM news_sources")
                    remaining = int(cursor.fetchone()["n"])
                    return {"message": "Tidak ada orphan.", "deleted": 0, "remaining": remaining}
                cursor.execute(
                    "DELETE FROM news_sources WHERE id NOT IN (SELECT DISTINCT source_id FROM mentions)"
                )
                deleted_count = cursor.rowcount or 0
                cursor.execute("SELECT COUNT(*) AS n FROM news_sources")
                remaining = int(cursor.fetchone()["n"])
        return {
            "message": f"Berhasil hapus {deleted_count} orphan news_sources.",
            "deleted": deleted_count,
            "remaining": remaining,
            "orphan_names_sample": [o["name"] for o in orphans[:20]],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup gagal: {e}")

@app.get("/summary")
async def summary(
    user=Depends(get_current_user),
    start_date: str | None = None,
    end_date: str | None = None,
):
    mentions = get_mentions_from_db(start_date, end_date)
    sentiment = {"positif": 0, "negatif": 0, "netral": 0}
    for item in mentions:
        s = item.get("sentiment", "netral")
        if s in sentiment:
            sentiment[s] += 1
    all_users = get_all_users()
    return {
        "total_mentions": len(mentions),
        "unique_authors": len(set(x["author"] for x in mentions if x.get("author"))),
        "total_users": len(all_users),
        "sentiment": sentiment,
    }

@app.get("/timeline")
async def get_timeline(
    current_user=Depends(get_current_user),
    start_date: str | None = None,
    end_date: str | None = None,
):
    mentions = get_mentions_from_db(start_date, end_date)
    date_counts = Counter(item["date"] for item in mentions if item.get("date"))
    sorted_dates = sorted(date_counts.items())
    return {"timeline": [{"date": d, "count": c} for d, c in sorted_dates]}

@app.get("/top-authors")
async def get_top_authors(
    current_user=Depends(get_current_user),
    start_date: str | None = None,
    end_date: str | None = None,
):
    mentions = get_mentions_from_db(start_date, end_date)
    author_counts = Counter(item["author"] for item in mentions if item.get("author"))
    return {"top_authors": [{"author": a, "count": c} for a, c in author_counts.most_common(10)]}

@app.get("/wordcloud")
async def get_wordcloud(
    current_user=Depends(get_current_user),
    start_date: str | None = None,
    end_date: str | None = None,
):
    mentions = get_mentions_from_db(start_date, end_date)
    stop_words = {
        "di", "ke", "dari", "dan", "yang", "untuk", "dengan", "pada",
        "ini", "itu", "dalam", "adalah", "jadi", "oleh", "akan",
        "atau", "bisa", "ada", "tidak", "lebih", "saat", "juga",
        "telah", "sudah", "dapat", "harus", "serta", "seperti",
        "namun", "masih", "karena", "agar", "bagi", "the", "and",
        "aja", "nya", "lah", "pun"
    }
    word_counts = Counter()
    for item in mentions:
        words = (item.get("title") or "").lower().replace(",", "").replace(".", "").split()
        for word in words:
            if word not in stop_words and len(word) > 2:
                word_counts[word] += 1
    return {"wordcloud": [{"text": w, "value": c} for w, c in word_counts.most_common(50)]}

@app.get("/mentions")
async def get_mentions(
    current_user=Depends(get_current_user),
    start_date: str | None = None,
    end_date: str | None = None,
):
    mentions = get_mentions_from_db(start_date, end_date)
    return {"mentions": mentions}

@app.get("/top-mentions")
async def get_top_mentions(
    current_user=Depends(get_current_user),
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 5,
):
    mentions = get_mentions_from_db(start_date, end_date)
    BASE_STOP = {
        "di", "ke", "dari", "dan", "yang", "untuk", "dengan", "pada",
        "ini", "itu", "dalam", "adalah", "the", "a", "an", "atau",
        "akan", "tidak", "telah", "sudah", "juga", "saja", "lebih",
        "agar", "bagi", "oleh", "saat", "karena", "namun", "masih",
        "para", "kita", "kami", "saya", "anda", "mereka", "nya",
        "lah", "kah", "pun", "se", "men", "ber",
    }

    def title_words(title: str) -> set[str]:
        cleaned = re.sub(r"[^\w\s]", " ", (title or "").lower())
        return {
            w for w in cleaned.split()
            if w not in BASE_STOP and len(w) > 2 and not w.isdigit()
        }

    word_doc_freq: dict[str, int] = {}
    valid_mentions: list[tuple[dict, set[str]]] = []
    for m in mentions:
        words = title_words(m.get("title") or "")
        if len(words) < 3:
            continue
        valid_mentions.append((m, words))
        for w in words:
            word_doc_freq[w] = word_doc_freq.get(w, 0) + 1

    total_docs = len(valid_mentions)
    if total_docs == 0:
        return {"top_mentions": []}

    domain_stop = {w for w, c in word_doc_freq.items() if c > total_docs * 0.85}
    signatures: list[tuple[dict, frozenset[str]]] = []
    for m, words in valid_mentions:
        sig = frozenset(words - domain_stop)
        if len(sig) >= 3:
            signatures.append((m, sig))

    JACCARD_THRESHOLD = 0.35
    MIN_SHARED_WORDS = 4
    clusters: list[dict] = []
    signatures.sort(key=lambda x: -len(x[1]))

    for m, sig in signatures:
        best_cluster = None
        best_score = 0.0
        for c in clusters:
            inter = sig & c["sig"]
            inter_size = len(inter)
            union_size = len(sig | c["sig"])
            score = inter_size / union_size if union_size else 0.0
            is_match = score >= JACCARD_THRESHOLD or inter_size >= MIN_SHARED_WORDS
            if is_match and score > best_score:
                best_score = score
                best_cluster = c
        if best_cluster:
            best_cluster["mentions"].append(m)
        else:
            clusters.append({"sig": sig, "mentions": [m]})

    def sort_key(c: dict):
        mc = len(c["mentions"])
        outlet_count = len({(x.get("author") or "").lower() for x in c["mentions"]})
        latest = max((x.get("date") or "") for x in c["mentions"])
        return (-mc, -outlet_count, latest)

    clusters.sort(key=sort_key)
    result = []
    for c in clusters[:limit]:
        group = c["mentions"]
        rep = max(group, key=lambda x: (x.get("date") or "", x.get("id", 0)))
        outlets = sorted({(x.get("author") or "Unknown") for x in group})
        sent_counts: dict[str, int] = {"positif": 0, "negatif": 0, "netral": 0}
        for x in group:
            s = x.get("sentiment") or "netral"
            sent_counts[s] = sent_counts.get(s, 0) + 1
        rep_sentiment = rep.get("sentiment") or "netral"
        result.append({
            "title": rep.get("title"),
            "url": rep.get("url"),
            "author": rep.get("author"),
            "date": rep.get("date"),
            "sentiment": rep_sentiment,
            "sentiment_breakdown": sent_counts,
            "outlet_count": len(outlets),
            "mention_count": len(group),
            "outlets": outlets[:8],
        })
    return {"top_mentions": result}

@app.get("/keyword-stats")
def keyword_stats(user=Depends(get_current_user)):
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT k.keyword AS name, COUNT(*) AS total
            FROM mention_keywords mk
            JOIN keywords k ON k.id = mk.keyword_id
            GROUP BY k.keyword
            ORDER BY total DESC
            """
        )
        return cursor.fetchall()

@app.patch("/mentions/{mention_id}")
async def update_mention_sentiment(
    mention_id: int,
    request: UpdateSentimentRequest,
    current_user=Depends(get_current_user),
):
    if request.sentiment not in {"positif", "negatif", "netral"}:
        raise HTTPException(status_code=400, detail="Invalid sentiment value")
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute(
                """
                UPDATE mentions SET sentiment = %s, updated_at = NOW()
                WHERE id = %s RETURNING id, title, author, sentiment
                """,
                (request.sentiment, mention_id)
            )
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Mention not found")
            return {"message": "Sentiment updated", "mention": dict(result)}

@app.delete("/mentions/{mention_id}")
async def delete_mention(
    mention_id: int,
    current_user=Depends(get_current_user),
):
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute(
                "DELETE FROM mentions WHERE id = %s RETURNING id",
                (mention_id,)
            )
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Mention not found")
            return {"message": "Mention deleted", "id": mention_id}

@app.get("/sentiment-breakdown")
async def get_sentiment_breakdown(
    current_user=Depends(get_current_user),
    start_date: str | None = None,
    end_date: str | None = None,
):
    mentions = get_mentions_from_db(start_date, end_date)
    sentiment_data = {"positif": [], "negatif": [], "netral": []}
    for item in mentions:
        s = item.get("sentiment", "netral")
        if s in sentiment_data:
            sentiment_data[s].append(item)
    return {
        "breakdown": sentiment_data,
        "counts": {k: len(v) for k, v in sentiment_data.items()}
    }


# ====================================
# SVM TRAINING & LABELING
# ====================================

from sentiment.evaluate import evaluate_predictions

VALID_SENTIMENT = {"positif", "negatif", "netral"}


class SentimentLabelRequest(BaseModel):
    label: str


@app.get("/svm/status")
async def svm_status(current_user=Depends(get_current_user)):
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE sentiment_svm IS NOT NULL) AS svm_filled,
                COUNT(*) FILTER (WHERE sentiment_label IS NOT NULL) AS labeled
            FROM mentions
            WHERE mention_date >= %s AND mention_date <= %s
            """,
            (MENTION_DATE_MIN, MENTION_DATE_MAX),
        )
        row = cursor.fetchone()
    return {
        "svm_available": SVM_MODEL is not None,
        "total_mentions": row["total"],
        "svm_predicted": row["svm_filled"],
        "labeled": row["labeled"],
    }

@app.get("/svm/predict")
async def svm_predict(text: str, current_user=Depends(get_current_user)):
    if SVM_MODEL is None:
        raise HTTPException(status_code=400, detail="Model SVM belum di-train")
    pred = analyze_sentiment_svm(text)
    return {"text": text, "sentiment": pred}

@app.get("/svm/sample")
async def svm_sample(
    current_user=Depends(get_current_user),
    limit: int = 50,
    only_unlabeled: bool = False,
):
    where_sql = "WHERE sentiment_label IS NULL" if only_unlabeled else ""
    sql = f"""
        SELECT id, title, author, url, sentiment_svm, sentiment_label,
               TO_CHAR(mention_date, 'YYYY-MM-DD') AS date
        FROM mentions {where_sql}
        ORDER BY mention_date DESC, id DESC LIMIT %s
    """
    with get_db_cursor() as cursor:
        cursor.execute(sql, (max(1, min(limit, 500)),))
        rows = cursor.fetchall()
    return {"items": [dict(r) for r in rows], "svm_available": SVM_MODEL is not None}

@app.get("/svm/metrics")
async def svm_metrics(current_user=Depends(get_current_user)):
    with get_db_cursor() as cursor:
        # Hitung total data berlabel manual
        cursor.execute(
            "SELECT COUNT(*) AS total FROM mentions WHERE sentiment_label IS NOT NULL"
        )
        total_labeled = cursor.fetchone()["total"]

        # Ambil data yang punya keduanya untuk hitung confusion matrix
        cursor.execute(
            """
            SELECT sentiment_svm, sentiment_label FROM mentions
            WHERE sentiment_label IS NOT NULL AND sentiment_svm IS NOT NULL
            """
        )
        rows = cursor.fetchall()
    if not rows:
        return {"labeled_count": 0, "svm_available": SVM_MODEL is not None,
                "message": "Belum ada mention berlabel + prediksi SVM."}
    y_true = [r["sentiment_label"] for r in rows]
    y_pred = [r["sentiment_svm"] for r in rows]
    metrics = evaluate_predictions(y_true, y_pred)
    return {"labeled_count": total_labeled, "svm_available": SVM_MODEL is not None, "metrics": metrics}

@app.get("/svm/training-metrics")
async def svm_training_metrics(current_user=Depends(get_current_user)):
    from sentiment.svm import DEFAULT_MODEL_PATH
    import json as _json
    metrics_path = DEFAULT_MODEL_PATH.parent / "metrics.json"
    if not metrics_path.exists():
        return {"available": False, "message": "Belum ada metrics.json."}
    return {"available": True, "metrics": _json.loads(metrics_path.read_text(encoding="utf-8"))}

@app.post("/svm/labels/{mention_id}")
async def submit_label(
    mention_id: int,
    request: SentimentLabelRequest,
    current_user=Depends(get_current_user),
):
    label = (request.label or "").strip().lower()
    if label not in VALID_SENTIMENT:
        raise HTTPException(status_code=400, detail="Invalid label")
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute(
                """
                UPDATE mentions SET sentiment_label = %s, updated_at = NOW()
                WHERE id = %s RETURNING id, title, sentiment_svm, sentiment_label
                """,
                (label, mention_id),
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Mention not found")
            return {"message": "Label tersimpan", "mention": dict(row)}

@app.delete("/svm/labels/{mention_id}")
async def clear_label(
    mention_id: int,
    current_user=Depends(get_current_user),
):
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute(
                "UPDATE mentions SET sentiment_label = NULL, updated_at = NOW() WHERE id = %s RETURNING id",
                (mention_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Mention not found")
            return {"message": "Label dihapus", "id": mention_id}

@app.post("/svm/predict-all")
async def svm_predict_all(admin=Depends(get_admin_user), repredict: bool = False):
    if SVM_MODEL is None:
        raise HTTPException(status_code=400, detail="Model SVM belum di-train")
    where = "" if repredict else "WHERE sentiment_svm IS NULL"
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute(f"SELECT id, title FROM mentions {where}")
            rows = cursor.fetchall()
            if not rows:
                return {"updated": 0, "message": "Tidak ada row yang perlu diprediksi."}
            titles = [r["title"] or "" for r in rows]
            details_list = SVM_MODEL.predict_with_details_batch(titles)
            # Bulk UPDATE pakai execute_values (single query, jauh lebih cepat)
            update_pairs = [
                (row["id"], det["label"])
                for row, det in zip(rows, details_list)
                if det and det.get("label")
            ]
            bulk_update_mention_sentiment(cursor, update_pairs)
            mention_ids = [pair[0] for pair in update_pairs]
            sa_inserted = bulk_upsert_sentiment_analysis(cursor, mention_ids, details_list)
            return {"updated": len(rows), "sentiment_analysis_rows": sa_inserted, "repredict": repredict}

@app.post("/svm/retrain")
async def svm_retrain(
    test_size: float = 0.2,
    seed: int = 42,
    admin=Depends(get_admin_user),
):
    """
    Train ulang SVM model.

    Query params:
    - test_size: proporsi test set (default 0.2 untuk 80:20).
                 Untuk 70:30 pakai test_size=0.3.
                 Untuk 75:25 pakai test_size=0.25.
    - seed: random_state untuk reproducibility (default 42).
    """
    global SVM_MODEL
    from sentiment.dataset import load_training_data
    from sentiment.svm import SVMSentimentClassifier, DEFAULT_MODEL_PATH
    from sklearn.model_selection import train_test_split
    import json as _json
    from datetime import datetime as _dt, timezone as _tz

    if not (0.05 <= test_size <= 0.5):
        raise HTTPException(400, "test_size harus 0.05 - 0.5")

    df, info = load_training_data(include_db_labels=True, seed_path=Path("nonexistent.csv"))
    if df["label"].nunique() < 2:
        raise HTTPException(status_code=400, detail="Dataset cuma punya 1 kelas")

    X = df["text"].tolist()
    y = df["label"].tolist()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed,
        stratify=y if df["label"].value_counts().min() >= 2 else None,
    )
    clf = SVMSentimentClassifier()
    print(f"[RETRAIN] Training SVM with max_features={clf.pipeline['tfidf'].max_features}, C={clf.pipeline['clf'].C}")
    clf.fit(X_train, y_train)
    saved_path = clf.save()

    y_pred_svm = clf.predict(X_test)
    svm_eval = evaluate_predictions(y_test, y_pred_svm)

    train_pct = int(round((1 - test_size) * 100))
    test_pct = int(round(test_size * 100))
    split_label = f"{train_pct}_{test_pct}"

    metrics = {
        "svm": svm_eval,
        "split": {
            "test_size": test_size,
            "train_size": round(1 - test_size, 4),
            "n_train": len(X_train),
            "n_test": len(X_test),
            "seed": seed,
            "label": f"{train_pct}:{test_pct}",
        },
        "meta": {
            "trained_at": _dt.now(_tz.utc).isoformat(),
            "data_info": info,
            "trigger": "api",
        },
    }
    # Simpan ke metrics.json (latest) + versi spesifik untuk perbandingan
    metrics_path = DEFAULT_MODEL_PATH.parent / "metrics.json"
    metrics_path.write_text(_json.dumps(metrics, indent=2, ensure_ascii=False))
    versioned_path = DEFAULT_MODEL_PATH.parent / f"metrics_split_{split_label}.json"
    versioned_path.write_text(_json.dumps(metrics, indent=2, ensure_ascii=False))
    SVM_MODEL = clf

    sa_inserted = 0
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute("SET statement_timeout = '120s'")
            cursor.execute(
    "SELECT id, title FROM mentions WHERE mention_date >= %s AND mention_date <= %s",
    (MENTION_DATE_MIN, MENTION_DATE_MAX)
)
            rows = cursor.fetchall()
            if rows:
                titles = [r["title"] or "" for r in rows]
                details_list = clf.predict_with_details_batch(titles)
                # Bulk UPDATE pakai execute_values (single query, jauh lebih cepat)
                update_pairs = [
                    (row["id"], det["label"])
                    for row, det in zip(rows, details_list)
                    if det and det.get("label")
                ]
                bulk_update_mention_sentiment(cursor, update_pairs)
                mention_ids = [pair[0] for pair in update_pairs]
                sa_inserted = bulk_upsert_sentiment_analysis(cursor, mention_ids, details_list)
            applied = len(rows)

    return {
        "message": "Model di-train ulang & ter-apply ke seluruh data",
        "sentiment_analysis_rows": sa_inserted,
        "model_path": str(saved_path),
        "data_info": info,
        "training_metrics": metrics,
        "applied": applied,
    }