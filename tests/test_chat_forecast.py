from app.chatbot import answer
from app.db import SessionLocal


def test_rain_forecast_question_gets_a_labelled_forecast():
    with SessionLocal() as db:
        r = answer(db, "rainfall forecast for Musanze")
    assert r["intent"] == "forecast"
    assert "Musanze" in r["reply"] and "SYNTHETIC" in r["reply"]


def test_forecast_until_2050_reaches_december_2050():
    with SessionLocal() as db:
        r = answer(db, "temperature forecast for Kirehe until 2050")
    assert "Dec 2050" in r["reply"]
    assert "not been tested" in r["reply"]


def test_historical_rainfall_question_still_uses_the_history_answer():
    with SessionLocal() as db:
        r = answer(db, "rainfall in Musanze in 2022")
    assert r["intent"] == "climate"


def test_named_month_gives_one_value_for_the_district():
    with SessionLocal() as db:
        r = answer(db, "what is the rain forecast in huye for july 2027")
    assert r["intent"] == "forecast"
    assert "Huye" in r["reply"] and "Jul 2027" in r["reply"]
    assert "Nov 2026" not in r["reply"] and "Aug 2027" not in r["reply"]


def test_forecast_without_a_district_gives_all_districts():
    with SessionLocal() as db:
        r = answer(db, "what is the rain forecast for july 2027")
    assert r["intent"] == "forecast"
    assert "all districts" in r["reply"]
    assert "Huye:" in r["reply"] and "Musanze:" in r["reply"]


def test_forecast_question_about_meaning_gets_the_explanation():
    with SessionLocal() as db:
        r = answer(db, "what does that forecast mean?")
    assert r["intent"] == "forecast_explanation"
    assert "80% range" in r["reply"]


def test_followup_compares_with_history_when_given_the_last_forecast():
    with SessionLocal() as db:
        first = answer(db, "rain forecast for huye for july 2027")
        r = answer(db, "is that higher than normal?", context=first["context"])
    assert r["intent"] == "forecast_followup"
    assert "Huye" in r["reply"] and "average" in r["reply"]