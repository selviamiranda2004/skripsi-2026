from sentiment.dataset import load_training_data
from sentiment.preprocessing import preprocess_text
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GridSearchCV, StratifiedKFold

df, info = load_training_data(include_db_labels=True, use_seed=False)
X = [preprocess_text(t) for t in df["text"]]
y = df["label"].tolist()

pipeline = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
    ("clf", LinearSVC(class_weight="balanced", max_iter=2000, random_state=42)),
])

param_grid = {
    'clf__C': [0.01, 0.03, 0.05, 0.1, 0.3, 0.5, 1.0],
    'tfidf__max_features': [1000],
    'tfidf__min_df': [2, 3],
}

skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
grid = GridSearchCV(pipeline, param_grid, cv=skf, scoring="f1_macro", n_jobs=-1)
grid.fit(X, y)

print("Best params:", grid.best_params_)
print("Best CV F1-macro:", grid.best_score_)

