"""IsokoBot wording suggestions (pair HMM + Viterbi) and the Yes / No choices."""
import pytest

from app.chatbot_suggest import CATALOGUE, similarity, suggest_question


def ask(client, text):
    return client.post("/api/chat", json={"message": text}).json()


def test_similarity_is_one_for_identical_text_and_lower_for_typos():
    assert similarity("distance to the market", "distance to the market") == 1.0
    assert 0.5 < similarity("distance to the market", "distnce to the markt") < 1.0
    assert similarity("distance to the market", "what is the capital of france") < 0.3


def test_user_example_suggests_the_households_question():
    assert suggest_question("distance to the market") == "the number of households within 1 km from the market"


def test_typos_still_get_the_suggestion():
    assert suggest_question("distnce to the markt") == "the number of households within 1 km from the market"


@pytest.mark.parametrize("text", ["what is the capital of france", "hello there", "who won the football match",
                                  "tell me a joke", "hi", ""])
def test_unrelated_text_gets_no_suggestion(text):
    assert suggest_question(text) is None


def test_ambiguous_wording_gets_no_guess():
    # "fertilizer use" is equally close to organic and inorganic fertiliser, so IsokoBot does not guess
    assert suggest_question("fertilizer use") is None


def test_suggestion_offers_yes_and_no_buttons(client):
    r = ask(client, "distance to the market")
    assert r["intent"] == "suggestion"
    assert r["reply"] == 'Did you mean "the number of households within 1 km from the market"?'
    assert r["choices"] == [{"label": "Yes", "ask": "the number of households within 1 km from the market"},
                            {"label": "No", "ask": None}]


def test_yes_choice_answers_the_suggested_question(client):
    suggested = ask(client, "distance to the market")["choices"][0]["ask"]
    r = ask(client, suggested)
    assert r["intent"] == "indicator"
    assert "within 1 km" in r["reply"].lower()


def test_unrelated_question_still_gets_the_fixed_reply(client):
    r = ask(client, "what is the capital of france")
    assert r["reply"] == "can't respond to this!" and r["choices"] == []


@pytest.mark.parametrize("entry", CATALOGUE, ids=lambda e: e["ask"][:40])
def test_every_catalogue_question_routes_to_a_real_answer(client, entry):
    r = ask(client, entry["ask"])
    assert r["intent"] not in ("unknown", "suggestion", "help"), (entry["ask"], r["intent"])
