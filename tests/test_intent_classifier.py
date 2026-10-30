"""IsokoBot intent classifier: what it predicts, and that it never changes the answers the rules already give."""
import pytest

from app.chatbot import answer
from app.db import SessionLocal
from app.ml import intent_classifier as ic
from app.ml.intent_data import CANONICAL, CHALLENGE, CLARIFY, OUT_OF_SCOPE, build, normalise_entities


def test_names_are_masked_before_classification():
    out = normalise_entities(["Is Musanze in the critical zone in 2010", "price of Irish potatoes in Huye"])
    assert out[0] == "is districtname in the critical zone in yearvalue"
    assert "districtname" in out[1] and "productname" in out[1]


def test_training_data_covers_every_intent():
    _, labels = build("all")
    assert set(labels) == set(CANONICAL) | set(CLARIFY) | {OUT_OF_SCOPE}


def test_training_is_deterministic():
    texts, labels = build("train")
    probe = ["which districts are critical", "tell me a joke", "rainfall in Musanze in 2022"]
    assert list(ic.fit(texts, labels).predict(probe)) == list(ic.fit(texts, labels).predict(probe))


def test_obvious_questions_are_recognised():
    assert ic.predict_intent("what is the weather on mars")[0] == OUT_OF_SCOPE
    intent, confidence = ic.predict_intent("which districts are in the critical zone")
    assert intent == "critical_zone" and confidence >= ic.HIGH


def test_challenge_accuracy_meets_the_recorded_floor():
    model = ic.get_model()
    texts = [t for t, _ in CHALLENGE]
    truth = [y for _, y in CHALLENGE]
    preds = list(model.predict(texts))
    accuracy = sum(p == t for p, t in zip(preds, truth)) / len(truth)
    assert accuracy >= 0.70, f"challenge accuracy {accuracy:.1%}"


def test_no_confident_wrong_answers_on_the_challenge_set():
    model = ic.get_model()
    texts = [t for t, _ in CHALLENGE]
    truth = [y for _, y in CHALLENGE]
    probs = model.predict_proba(texts)
    preds = model.classes_[probs.argmax(axis=1)]
    wrong_and_confident = [t for t, p, c, y in zip(texts, preds, probs.max(axis=1), truth)
                           if c >= ic.HIGH and p != y]
    assert not wrong_and_confident, wrong_and_confident


@pytest.mark.parametrize("intent", list(CANONICAL))
def test_each_no_entity_intent_has_a_rule_answer(intent):
    with SessionLocal() as db:
        r = answer(db, CANONICAL[intent])
    assert r["intent"] not in ("unknown", "suggestion") and not r["intent"].startswith("classifier:"), (intent, r["intent"])


@pytest.mark.parametrize("text", [t for t, y in CHALLENGE if y == OUT_OF_SCOPE])
def test_out_of_scope_questions_get_the_refusal(client, text):
    r = client.post("/api/chat", json={"message": text}).json()
    assert r["reply"] == "can't respond to this!" and r["choices"] == []


def test_classifier_answers_a_question_the_rules_miss_and_says_which_it_answered():
    with SessionLocal() as db:
        r = answer(db, "where do the figures come from")
    assert r["intent"] == "classifier:sources"
    assert r["reply"].startswith('I think you are asking: "which data sources are used".')
    assert "Data sources recorded in the app" in r["reply"]


def test_price_words_without_a_product_still_get_the_product_prompt():
    with SessionLocal() as db:
        r = answer(db, "how do I write up a price I saw")
    assert r["intent"] == "ask_product"  # the existing rule has priority over the classifier


def test_good_alone_is_not_treated_as_a_colour_question():
    with SessionLocal() as db:
        r = answer(db, "what is a good price for maize")
    assert r["intent"] != "colour_meaning" and r["intent"] != "district_status_summary"
