"""IsokoBot intent classifier: character n-gram TF-IDF with calibrated logistic regression.

The classifier chooses which kind of answer a question needs. It is used only after the rules and the
wording suggester have found nothing, so it cannot change any answer that already works.

Why character n-grams: they cope with spelling mistakes, missing letters and mixed spelling
(fertiliser and fertilizer), and they need no internet download or large model.

Confidence: the probabilities are calibrated with a sigmoid fit (cross-validated), so a score of 0.7 should
be right about 70 per cent of the time. The thresholds below decide what IsokoBot does with each score.

The trained model is saved to app/ml/artifacts/intent_model.joblib by
`python -m app.ml.evaluate_intents`. If the file is missing, the model is trained when first needed.
"""
import threading
from pathlib import Path

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer

from .intent_data import OUT_OF_SCOPE, build, normalise_entities

HIGH = 0.70    # at or above this: act (answer, or ask for the missing detail). Chosen on the held-out templates.
MEDIUM = 0.50  # at or above this (and below HIGH): offer a Yes/No suggestion for questions that need no entity
ARTIFACT = Path(__file__).parent / "artifacts" / "intent_model.joblib"

_model = None
_lock = threading.Lock()


def build_pipeline():
    masking = FunctionTransformer(normalise_entities)  # district, product, year names become placeholders
    vectoriser = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)
    base = LogisticRegression(C=10.0, max_iter=5000, class_weight="balanced")
    return make_pipeline(masking, vectoriser, CalibratedClassifierCV(base, method="sigmoid", cv=3))


def fit(texts: list[str], labels: list[str]):
    return build_pipeline().fit(texts, labels)


def get_model():
    global _model
    with _lock:
        if _model is None:
            if ARTIFACT.exists():
                import joblib
                _model = joblib.load(ARTIFACT)
            else:
                texts, labels = build("all")
                _model = fit(texts, labels)
        return _model


def predict_intent(text: str) -> tuple[str, float]:
    """The most likely intent for a question, and its calibrated probability."""
    model = get_model()
    probs = model.predict_proba([text])[0]
    best = int(np.argmax(probs))
    return str(model.classes_[best]), float(probs[best])


def is_out_of_scope(intent: str) -> bool:
    return intent == OUT_OF_SCOPE
