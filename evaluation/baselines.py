"""
Two intent-classification baselines, both trained only on the 296 usable
DISCOVERY-phase examples (see evaluation/data_loading.py). No golden-200 data
is ever used to fit, tune, or select hyperparameters for either baseline --
golden-200 is evaluation-only.

Deliberately not over-tuned: standard/default scikit-learn hyperparameters,
fixed random seed (config.BASELINE_SEED), no grid search.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


class MajorityClassBaseline:
    """Predicts the single most frequent training label for every input. The floor baseline."""

    def __init__(self):
        self.majority_label_ = None
        self.label_counts_ = None

    def fit(self, labels):
        self.label_counts_ = Counter(labels)
        self.majority_label_ = self.label_counts_.most_common(1)[0][0]
        return self

    def predict(self, texts):
        if self.majority_label_ is None:
            raise RuntimeError("MajorityClassBaseline.fit() must be called before predict().")
        return [self.majority_label_] * len(texts)


class TfidfLogRegBaseline:
    """TF-IDF (fit on training texts only) + multinomial Logistic Regression."""

    def __init__(self):
        self.vectorizer = TfidfVectorizer(**config.TFIDF_PARAMS)
        self.classifier = LogisticRegression(**config.LOGREG_PARAMS)
        self._fitted = False

    def fit(self, texts, labels):
        X = self.vectorizer.fit_transform(texts)  # vocabulary fit on the 296 training texts only
        self.classifier.fit(X, labels)
        self._fitted = True
        return self

    def predict(self, texts):
        if not self._fitted:
            raise RuntimeError("TfidfLogRegBaseline.fit() must be called before predict().")
        X = self.vectorizer.transform(texts)  # transform only -- no re-fitting on eval data
        return list(self.classifier.predict(X))
