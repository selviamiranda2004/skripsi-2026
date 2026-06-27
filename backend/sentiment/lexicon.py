"""
Lexicon-based (rule-based) sentiment analyzer.

This is the legacy method previously embedded in main.py. It counts
positive vs negative keyword occurrences and returns the dominant label.
Kept here so it can be compared head-to-head against the SVM model.
"""

POSITIVE_KEYWORDS: list[str] = [
    "meningkat", "naik", "sukses", "berhasil", "tumbuh", "maju", "baik",
    "positif", "untung", "laba", "ekspor", "raih", "capai", "inovasi",
    "dorong", "dukung", "bantu", "program", "pengembangan", "peluang",
    "prestasi", "penghargaan", "kolaborasi", "solusi", "optimis", "peningkatan",
    "berkembang", "sejahtera", "produktif", "efisien", "unggul", "juara",
    "luncurkan", "tingkatkan", "perkuat", "manfaat", "kemajuan", "harapan",
]

NEGATIVE_KEYWORDS: list[str] = [
    "turun", "rugi", "gagal", "masalah", "kendala", "hambatan", "sulit",
    "tantangan", "ancaman", "krisis", "terpuruk", "bangkrut", "lesu",
    "menurun", "terdampak", "terkendala", "persaingan", "ketat", "impor",
    "terhambat", "merosot", "rendah", "lemah", "jelek", "buruk", "mati",
    "gulung tikar", "kolaps", "defisit", "inflasi", "mahal", "susah",
]


def analyze_sentiment_lexicon(text: str) -> str:
    """Return 'positif' / 'negatif' / 'netral' based on keyword count."""
    if not text:
        return "netral"
    text_lower = text.lower()
    pos_score = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    neg_score = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
    if pos_score > neg_score:
        return "positif"
    if neg_score > pos_score:
        return "negatif"
    return "netral"
