"""
Text preprocessing for Indonesian sentiment classification.

Pipeline:
  1. Lowercase
  2. Remove URLs
  3. Remove non-letter characters (keep latin letters + spaces)
  4. Tokenize (whitespace)
  5. Remove Indonesian + English common stopwords
  6. (Optional) Stem with Sastrawi (Indonesian)

Sastrawi import is wrapped in try/except so the module still imports
even before the package is installed (lets the lexicon module work).
The CLI trainer & SVM predictor will fail loudly if Sastrawi missing.
"""

from __future__ import annotations

import re
from functools import lru_cache

# ---------------------------------------------------------------------------
# Stopwords (Bahasa Indonesia + a few English fillers that leak via Google News)
# ---------------------------------------------------------------------------
STOPWORDS: set[str] = {
    # Indonesian function words
    "yang", "untuk", "dengan", "pada", "ini", "itu", "dalam", "adalah",
    "dari", "dan", "atau", "akan", "tidak", "telah", "sudah", "juga",
    "saja", "lebih", "agar", "bagi", "oleh", "saat", "karena", "namun",
    "masih", "para", "kita", "kami", "saya", "anda", "mereka", "nya",
    "lah", "kah", "pun", "dia", "ia", "se", "men", "ber", "di", "ke",
    "yg", "tsb", "dll", "dsb", "bisa", "ada", "ialah", "yakni", "yaitu",
    "hanya", "demi", "tapi", "tetapi", "sebagai", "menjadi", "antara",
    "maupun", "sambil", "selain", "setelah", "sebelum", "ketika", "sejak",
    "terhadap", "tentang", "mengenai", "begitu", "sehingga",
    # English fillers from Google News titles
    "the", "and", "for", "with", "from", "this", "that", "are", "was",
    "were", "has", "have", "had", "will", "would", "should", "can",
}


def _basic_clean(text: str) -> str:
    """Lowercase + strip URLs + keep only letters/spaces."""
    if not text:
        return ""
    text = text.lower()
    # remove URLs
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    # remove anything that's not a-z or whitespace (drops digits & punctuation)
    text = re.sub(r"[^a-z\s]", " ", text)
    # collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


@lru_cache(maxsize=1)
def _get_stemmer():
    """Lazy-load Sastrawi stemmer (heavy import). Cached process-wide."""
    try:
        from Sastrawi.Stemmer.StemmerFactory import StemmerFactory  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "Sastrawi belum terinstall. Jalankan: uv pip install Sastrawi"
        ) from e
    return StemmerFactory().create_stemmer()


@lru_cache(maxsize=20_000)
def _stem_word(word: str) -> str:
    """Stem a single word, cached. Sastrawi is slow per-call."""
    return _get_stemmer().stem(word)


def preprocess_text(
    text: str,
    use_stemmer: bool = True,
    remove_stopwords: bool = True,
    min_word_len: int = 2,
) -> str:
    """
    Clean -> tokenize -> (stopword filter) -> (stem) -> rejoin.

    Returns a single space-separated string ready for TfidfVectorizer.
    """
    cleaned = _basic_clean(text)
    if not cleaned:
        return ""

    tokens = cleaned.split()

    if remove_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS and len(t) >= min_word_len]

    if use_stemmer:
        tokens = [_stem_word(t) for t in tokens]

    return " ".join(tokens)


def preprocess_batch(
    texts: list[str],
    use_stemmer: bool = True,
    remove_stopwords: bool = True,
) -> list[str]:
    """Convenience wrapper."""
    return [
        preprocess_text(t, use_stemmer=use_stemmer, remove_stopwords=remove_stopwords)
        for t in texts
    ]
