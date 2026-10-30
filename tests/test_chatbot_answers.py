"""IsokoBot answers the question asked: climate by district and year, indicator gaps, and unrelated questions."""
from app.db import SessionLocal
from app.models import ClimateObservation


def ask(client, text):
    return client.post("/api/chat", json={"message": text}).json()


def test_rainfall_question_quotes_the_climate_table(client):
    r = ask(client, "rainfall in Musanze in 2022")
    assert r["intent"] == "climate" and "Musanze, 2022:" in r["reply"] and "mm of rain" in r["reply"]
    assert "DEMO DATA" in r["reply"]
    with SessionLocal() as db:
        rain = sum(c.rain_mm for c in db.query(ClimateObservation).filter_by(district="Musanze", year=2022))
    assert f"{rain:,.0f} mm of rain" in r["reply"]


def test_climate_year_outside_the_data(client):
    assert ask(client, "rainfall in Musanze in 2030")["reply"].startswith("No data found for 2030")


def test_indicator_gap_says_which_years_are_covered(client):
    r = ask(client, "fertilizer use in Kayonza season A 2015")
    assert "no value in the data" in r["reply"] and "covers 2021 to 2026" in r["reply"]


def test_unrelated_weather_question_is_refused(client):
    assert ask(client, "what is the weather on mars")["reply"] == "can't respond to this!"


def test_unrelated_question_is_refused(client):
    assert ask(client, "who is the president of rwanda")["reply"] == "can't respond to this!"


def test_price_with_a_year_answers_that_period(client):
    r = ask(client, "price of beef in 2020")
    assert r["intent"] == "price_period" and "1 January 2020 to 31 December 2020" in r["reply"]
