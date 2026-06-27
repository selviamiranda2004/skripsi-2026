-- =====================================================
-- MEDIA MONITORING - DATABASE SCHEMA
-- Lightweight, indexed, with RLS
-- =====================================================
-- Cara pakai:
--   1. Buka Supabase Dashboard -> SQL Editor
--   2. Paste seluruh isi file ini
--   3. Run
--
-- Script ini IDEMPOTENT (boleh dijalanin berkali-kali).
-- Semua tabel, index, dan policy di-DROP dulu sebelum di-CREATE ulang.
-- =====================================================

-- Extension untuk bcrypt password hash
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- =====================================================
-- 1. DROP EXISTING (urutan reverse FK)
-- =====================================================
DROP TABLE IF EXISTS public.sentiment_analysis CASCADE;
DROP TABLE IF EXISTS public.mention_keywords   CASCADE;
DROP TABLE IF EXISTS public.mentions           CASCADE;
DROP TABLE IF EXISTS public.keywords           CASCADE;
DROP TABLE IF EXISTS public.news_sources       CASCADE;
DROP TABLE IF EXISTS public.users              CASCADE;


-- =====================================================
-- 2. TABLES
-- =====================================================

-- USERS (auth)
CREATE TABLE public.users (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username      VARCHAR NOT NULL UNIQUE,
    email         VARCHAR NOT NULL UNIQUE,
    password_hash VARCHAR NOT NULL,
    full_name     VARCHAR,
    role          VARCHAR NOT NULL DEFAULT 'viewer',
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

-- NEWS SOURCES (Google News, dll)
CREATE TABLE public.news_sources (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       VARCHAR NOT NULL,
    slug       VARCHAR NOT NULL UNIQUE,
    url        TEXT    NOT NULL,
    category   VARCHAR,
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- KEYWORDS (kata kunci pencarian)
CREATE TABLE public.keywords (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    keyword    VARCHAR NOT NULL UNIQUE,
    category   VARCHAR,
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- MENTIONS (artikel hasil scrape)
-- sentiment           : nilai aktif yang dipakai dashboard (default = lexicon)
-- sentiment_lexicon   : prediksi metode rule-based / kamus
-- sentiment_svm       : prediksi metode SVM (kosong sampai model di-train)
-- sentiment_label     : ground truth manual (diisi via labeling UI, untuk eval)
CREATE TABLE public.mentions (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title             VARCHAR NOT NULL,
    content           TEXT,
    source_id         BIGINT  NOT NULL REFERENCES public.news_sources(id),
    author            VARCHAR,
    url               TEXT UNIQUE,
    sentiment         VARCHAR CHECK (sentiment         IN ('positif','negatif','netral')),
    sentiment_lexicon VARCHAR CHECK (sentiment_lexicon IN ('positif','negatif','netral')),
    sentiment_svm     VARCHAR CHECK (sentiment_svm     IN ('positif','negatif','netral')),
    sentiment_label   VARCHAR CHECK (sentiment_label   IN ('positif','negatif','netral')),
    mention_date      TIMESTAMP NOT NULL,
    created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

-- MENTION_KEYWORDS (junction many-to-many)
-- UNIQUE (mention_id, keyword_id) wajib supaya ON CONFLICT DO NOTHING di backend jalan
CREATE TABLE public.mention_keywords (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mention_id BIGINT NOT NULL REFERENCES public.mentions(id) ON DELETE CASCADE,
    keyword_id BIGINT NOT NULL REFERENCES public.keywords(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (mention_id, keyword_id)
);

-- SENTIMENT ANALYSIS (detail analisis - optional)
CREATE TABLE public.sentiment_analysis (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mention_id       BIGINT NOT NULL REFERENCES public.mentions(id) ON DELETE CASCADE,
    sentiment_score  NUMERIC,
    confidence       NUMERIC,
    analysis_details JSONB,
    created_at       TIMESTAMP NOT NULL DEFAULT NOW()
);


-- =====================================================
-- 3. INDEXES (optimasi query backend)
-- =====================================================

-- mentions: timeline desc, filter sentiment, top-authors, JOIN source
CREATE INDEX idx_mentions_date_desc         ON public.mentions (mention_date DESC);
CREATE INDEX idx_mentions_sentiment         ON public.mentions (sentiment);
CREATE INDEX idx_mentions_sentiment_lexicon ON public.mentions (sentiment_lexicon);
CREATE INDEX idx_mentions_sentiment_svm     ON public.mentions (sentiment_svm);
CREATE INDEX idx_mentions_sentiment_label   ON public.mentions (sentiment_label);
CREATE INDEX idx_mentions_author            ON public.mentions (author);
CREATE INDEX idx_mentions_source            ON public.mentions (source_id);

-- mention_keywords: JOIN dua arah
CREATE INDEX idx_mk_mention ON public.mention_keywords (mention_id);
CREATE INDEX idx_mk_keyword ON public.mention_keywords (keyword_id);

-- sentiment_analysis: lookup by mention
CREATE INDEX idx_sa_mention ON public.sentiment_analysis (mention_id);

-- users: lookup by username untuk login (UNIQUE sudah otomatis bikin index)
-- (tidak perlu index tambahan)


-- =====================================================
-- 4. ROW LEVEL SECURITY (RLS)
-- =====================================================
-- Backend pakai DATABASE_URL (postgres role) -> BYPASS RLS otomatis.
-- Kebijakan di bawah ini cuma aktif untuk anon/authenticated dari Supabase client.
-- =====================================================

ALTER TABLE public.users              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.news_sources       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.keywords           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mentions           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mention_keywords   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sentiment_analysis ENABLE ROW LEVEL SECURITY;

-- ---- READ POLICY UNTUK DASHBOARD PUBLIK ----
-- (frontend bisa pakai anon key untuk SELECT, tapi tidak INSERT/UPDATE/DELETE)

CREATE POLICY "public_read_news_sources"
  ON public.news_sources FOR SELECT
  TO anon, authenticated
  USING (is_active = TRUE);

CREATE POLICY "public_read_keywords"
  ON public.keywords FOR SELECT
  TO anon, authenticated
  USING (is_active = TRUE);

CREATE POLICY "public_read_mentions"
  ON public.mentions FOR SELECT
  TO anon, authenticated
  USING (TRUE);

CREATE POLICY "public_read_mention_keywords"
  ON public.mention_keywords FOR SELECT
  TO anon, authenticated
  USING (TRUE);

CREATE POLICY "public_read_sentiment_analysis"
  ON public.sentiment_analysis FOR SELECT
  TO anon, authenticated
  USING (TRUE);

-- ---- USERS: NO PUBLIC ACCESS ----
-- Tidak ada policy = anon & authenticated tidak bisa SELECT/INSERT/UPDATE/DELETE.
-- Backend (postgres role) bypass RLS, jadi tetap bisa query users untuk auth.


-- =====================================================
-- 5. SEED DATA (data minimum biar app langsung jalan)
-- =====================================================

-- 5.1. News sources di-auto-create oleh backend per publisher RSS
--      (Tribun News, Liputan6, Kompas, dll). Tidak perlu seed manual.
--      Backend pakai INSERT ... ON CONFLICT (slug) DO UPDATE RETURNING id.

-- 5.2. Keywords sesuai SEARCH_KEYWORDS di backend/main.py
INSERT INTO public.keywords (keyword, category) VALUES
  ('Kementerian UMKM',   'kementerian'),
  ('Maman Abdurrahman',  'tokoh'),
  ('Helvi Moraza',       'tokoh'),
  ('Wakil Menteri UMKM', 'jabatan'),
  ('Deputi UMKM',        'jabatan'),
  ('Menteri UMKM',       'jabatan');

-- 5.3. Default admin user
--      username: admin
--      password: admin123
--      Hash bcrypt dari pgcrypto (kompatibel dengan Python bcrypt.checkpw)
--      Kalau login admin gagal setelah ini, jalankan: python seed_admin.py
INSERT INTO public.users (username, email, password_hash, full_name, role) VALUES
  ('admin',
   'admin@example.com',
   crypt('admin123', gen_salt('bf', 12)),
   'Administrator',
   'admin');


-- =====================================================
-- DONE
-- =====================================================
-- Verifikasi:
SELECT 'users'              AS tbl, COUNT(*) FROM public.users
UNION ALL SELECT 'news_sources',     COUNT(*) FROM public.news_sources
UNION ALL SELECT 'keywords',         COUNT(*) FROM public.keywords
UNION ALL SELECT 'mentions',         COUNT(*) FROM public.mentions
UNION ALL SELECT 'mention_keywords', COUNT(*) FROM public.mention_keywords
UNION ALL SELECT 'sentiment_analysis', COUNT(*) FROM public.sentiment_analysis;
