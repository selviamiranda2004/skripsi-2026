"""
Sentiment analysis package.

Sub-modules:
  - lexicon       : rule-based (current method)
  - preprocessing : text cleaning, tokenization, stopword removal, stemming
  - svm           : TF-IDF + LinearSVC pipeline (train / predict / save / load)
  - dataset       : load training data (bundled CSV + DB labels)
  - evaluate      : metrics (accuracy, precision, recall, F1, confusion matrix)
"""

from .lexicon import analyze_sentiment_lexicon, POSITIVE_KEYWORDS, NEGATIVE_KEYWORDS
from .preprocessing import preprocess_text
from .svm import SVMSentimentClassifier, load_default_model

__all__ = [
    "analyze_sentiment_lexicon",
    "POSITIVE_KEYWORDS",
    "NEGATIVE_KEYWORDS",
    "preprocess_text",
    "SVMSentimentClassifier",
    "load_default_model",
]
