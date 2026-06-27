"""
Train SVM sentiment classifier dan simpan model + metrik.

Cara pakai:
  cd backend
  python train_sentiment.py                  # train + eval default
  python train_sentiment.py --no-stemmer     # tanpa Sastrawi (lebih cepat)
  python train_sentiment.py --no-db          # ignore label dari DB
  python train_sentiment.py --test-size 0.25 # ubah ratio split

Output:
  backend/models/svm_sentiment.joblib   <- pipeline tersimpan
  backend/models/metrics.json           <- akurasi/F1 lexicon vs SVM
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sklearn.model_selection import train_test_split

from sentiment.dataset import load_training_data
from sentiment.evaluate import compare_methods, text_report
from sentiment.lexicon import analyze_sentiment_lexicon
from sentiment.svm import SVMSentimentClassifier, DEFAULT_MODEL_PATH

METRICS_PATH = DEFAULT_MODEL_PATH.parent / "metrics.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train SVM sentiment classifier")
    parser.add_argument("--no-stemmer", action="store_true",
                        help="Skip Sastrawi stemmer (lebih cepat, akurasi sedikit turun)")
    parser.add_argument("--no-db", action="store_true",
                        help="Jangan gabung label manual dari DB")
    parser.add_argument("--test-size", type=float, default=0.2,
                        help="Proporsi test set (default 0.2)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed untuk train/test split")
    parser.add_argument("--C", type=float, default=1.0,
                        help="Regularization parameter LinearSVC (default 1.0)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 60)
    print(" 🚀 TRAIN SVM SENTIMENT CLASSIFIER")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Load data
    # ------------------------------------------------------------------
    df, info = load_training_data(include_db_labels=not args.no_db)

    print(f"\n[1/4] Dataset")
    print(f"   - seed CSV  : {info['seed_rows']} rows  -> {info['seed_distribution']}")
    print(f"   - DB labels : {info['db_rows']} rows  -> {info['db_distribution']}")
    print(f"   - total     : {info['total_rows']} rows")
    print(f"   - distribusi: {df['label'].value_counts().to_dict()}")

    if df["label"].nunique() < 2:
        print("\n❌ Dataset hanya punya 1 kelas, tidak bisa training")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 2. Split train / test
    # ------------------------------------------------------------------
    X = df["text"].tolist()
    y = df["label"].tolist()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=args.test_size,
        random_state=args.seed,
        stratify=y if df["label"].value_counts().min() >= 2 else None,
    )
    print(f"\n[2/4] Split")
    print(f"   - train: {len(X_train)} rows")
    print(f"   - test : {len(X_test)} rows")

    # ------------------------------------------------------------------
    # 3. Train SVM
    # ------------------------------------------------------------------
    print(f"\n[3/4] Training SVM (stemmer={not args.no_stemmer}, C={args.C})...")
    clf = SVMSentimentClassifier(
        use_stemmer=not args.no_stemmer,
        C=args.C,
    )
    clf.fit(X_train, y_train)
    saved_path = clf.save()
    print(f"   - model disimpan ke: {saved_path}")

    # ------------------------------------------------------------------
    # 4. Evaluasi: SVM vs Lexicon di test set
    # ------------------------------------------------------------------
    print("\n[4/4] Evaluasi pada TEST SET (head-to-head)")
    y_pred_svm = clf.predict(X_test)
    y_pred_lex = [analyze_sentiment_lexicon(t) for t in X_test]

    print(text_report("LEXICON (rule-based)", y_test, y_pred_lex))
    print(text_report("SVM (TF-IDF + LinearSVC)", y_test, y_pred_svm))

    metrics = compare_methods(y_test, y_pred_lex, y_pred_svm)
    metrics["meta"] = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "use_stemmer": not args.no_stemmer,
            "test_size": args.test_size,
            "seed": args.seed,
            "C": args.C,
            "include_db_labels": not args.no_db,
        },
        "data_info": info,
    }

    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
    print(f"\n📊 Metrik disimpan ke: {METRICS_PATH}")

    # Ringkasan pendek
    print("\n" + "=" * 60)
    print(" 📈 RINGKASAN")
    print("=" * 60)
    lex_acc = metrics["lexicon"]["accuracy"]
    svm_acc = metrics["svm"]["accuracy"]
    lex_f1  = metrics["lexicon"]["macro_f1"]
    svm_f1  = metrics["svm"]["macro_f1"]
    delta_acc = svm_acc - lex_acc
    delta_f1  = svm_f1 - lex_f1
    print(f" Accuracy   :  Lexicon {lex_acc:.3f}  vs  SVM {svm_acc:.3f}  (Δ {delta_acc:+.3f})")
    print(f" Macro F1   :  Lexicon {lex_f1:.3f}  vs  SVM {svm_f1:.3f}  (Δ {delta_f1:+.3f})")
    print(f" Agreement  :  {metrics['agreement_rate']*100:.1f}%  (kedua metode sepakat)")
    print("=" * 60)
    print(" ✅ Selesai. Restart backend supaya model terload.")


if __name__ == "__main__":
    main()
