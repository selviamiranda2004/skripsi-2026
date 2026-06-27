"""
SVM sentiment classifier with TF-IDF features.

Pipeline:
  preprocess_text  ->  TfidfVectorizer (1-2 grams)  ->  LinearSVC

Notes:
  - LinearSVC dipilih karena cepat, scale-friendly untuk teks pendek,
    dan jadi baseline standar untuk text classification.
  - Probabilitas tidak native di LinearSVC, jadi kita expose
    decision_function() dan turunin pseudo-confidence kalau perlu.
  - Model + vectorizer disimpan satu file pakai joblib (Pipeline).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from .preprocessing import preprocess_text

# Default model location (relative to backend/)
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "svm_sentiment.joblib"

LABELS = ("positif", "negatif", "netral")


class SVMSentimentClassifier:
    """Thin wrapper di atas sklearn Pipeline supaya pemanggilan sederhana."""

    def __init__(
        self,
        ngram_range: tuple[int, int] = (1, 2),
        min_df: int = 2,
        max_df: float = 0.95,
        max_features: int | None = 5000,
        C: float = 1.0,
        use_stemmer: bool = True,
        random_state: int = 42,
    ):
        self.use_stemmer = use_stemmer
        self.pipeline: Pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                ngram_range=ngram_range,
                min_df=min_df,
                max_df=max_df,
                max_features=max_features,
                sublinear_tf=True,
            )),
            ("clf", LinearSVC(
                C=C,
                class_weight="balanced",
                max_iter=2000,
                random_state=random_state,
            )),
        ])
        self._fitted = False

    # ---------------- internal ----------------
    def _prep(self, texts: Iterable[str]) -> list[str]:
        return [preprocess_text(t, use_stemmer=self.use_stemmer) for t in texts]

    # ---------------- public API ----------------
    def fit(self, texts: list[str], labels: list[str]) -> "SVMSentimentClassifier":
        if len(texts) != len(labels):
            raise ValueError("texts dan labels harus sama panjang")
        if len(texts) == 0:
            raise ValueError("training set kosong")

        prepped = self._prep(texts)
        self.pipeline.fit(prepped, labels)
        self._fitted = True
        return self

    def predict(self, texts: list[str]) -> list[str]:
        if not self._fitted:
            raise RuntimeError("Model belum di-fit / di-load")
        prepped = self._prep(texts)
        return list(self.pipeline.predict(prepped))

    def predict_one(self, text: str) -> str:
        return self.predict([text])[0]

    def decision_scores(self, texts: list[str]) -> np.ndarray:
        """Return raw decision values (for diagnostic / ranking)."""
        if not self._fitted:
            raise RuntimeError("Model belum di-fit / di-load")
        prepped = self._prep(texts)
        return self.pipeline.decision_function(prepped)

    # ---------------- detailed prediction (untuk sentiment_analysis table) ----------------
    def predict_with_details_batch(self, texts: list[str]) -> list[dict]:
        """
        Versi batch dari predict_with_details.

        Output per item:
          {
            "label": "negatif",
            "scores":  {"positif": -0.56, "netral": -0.56, "negatif": 0.027},
            "softmax": {"positif": 0.21,  "netral": 0.21,  "negatif": 0.58},
            "confidence": 0.58,        # softmax dari predicted class
            "score":      0.027,       # decision_function dari predicted class
            "preprocessed_text": "menteri maman banjir keluh ..."
          }

        Catatan:
          - LinearSVC tidak punya `predict_proba` native. Kita derive
            pseudo-probability via softmax atas decision_function. Ini umum
            dipakai sebagai approximate confidence walaupun bukan kalibrasi
            penuh seperti Platt scaling.
        """
        if not self._fitted:
            raise RuntimeError("Model belum di-fit / di-load")
        if not texts:
            return []

        prepped = self._prep(texts)
        labels = self.pipeline.predict(prepped)
        scores_matrix = np.atleast_2d(self.pipeline.decision_function(prepped))
        classes = list(self.pipeline.named_steps["clf"].classes_)

        # Softmax baris-per-baris (numerically stable)
        shifted = scores_matrix - scores_matrix.max(axis=1, keepdims=True)
        exp_s = np.exp(shifted)
        softmax_matrix = exp_s / exp_s.sum(axis=1, keepdims=True)

        out: list[dict] = []
        for i, label in enumerate(labels):
            scores_row = scores_matrix[i]
            sm_row = softmax_matrix[i]
            label_str = str(label)
            try:
                idx = classes.index(label_str)
            except ValueError:
                idx = int(np.argmax(scores_row))
            out.append({
                "label": label_str,
                "scores":  {str(c): float(s) for c, s in zip(classes, scores_row)},
                "softmax": {str(c): float(s) for c, s in zip(classes, sm_row)},
                "confidence": float(sm_row[idx]),
                "score": float(scores_row[idx]),
                "preprocessed_text": prepped[i],
            })
        return out

    def predict_with_details(self, text: str) -> dict:
        """Single-item version of predict_with_details_batch."""
        return self.predict_with_details_batch([text])[0]

    # ---------------- persistence ----------------
    def save(self, path: str | Path = DEFAULT_MODEL_PATH) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {"pipeline": self.pipeline, "use_stemmer": self.use_stemmer},
            path,
        )
        return path

    @classmethod
    def load(cls, path: str | Path = DEFAULT_MODEL_PATH) -> "SVMSentimentClassifier":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Model file tidak ditemukan: {path}")
        bundle = joblib.load(path)
        inst = cls(use_stemmer=bundle.get("use_stemmer", True))
        inst.pipeline = bundle["pipeline"]
        inst._fitted = True
        return inst


def load_default_model() -> SVMSentimentClassifier | None:
    """Try to load the default model. Return None if missing (so app still boots)."""
    try:
        return SVMSentimentClassifier.load()
    except FileNotFoundError:
        return None
