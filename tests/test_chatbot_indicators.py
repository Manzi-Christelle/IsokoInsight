"""IsokoBot answers district indicator questions with the stored value for that district and year."""
from app.db import SessionLocal
from app.models import IndicatorValue


def ask(client, text):
    r = client.post("/api/chat", json={"message": text})
    assert r.status_code == 200
    return r.json()


def _stored(indicator, district, year, season=""):
    with SessionLocal() as db:
        return db.query(IndicatorValue.value).filter_by(indicator=indicator, district=district, year=year,
                                                        season=season).scalar()


def test_grain_reserve_in_a_district_and_year_quotes_that_value(client):
    expected = _stored("grain_reserve", "Musanze", 2010)
    r = ask(client, "grains held in reserve in musanze in 2010")
    assert r["intent"] == "indicator"
    assert f"Grain held in reserve in Musanze, 2010: {expected:,.1f} thousand kg." in r["reply"]
    assert "Good (green)" not in r["reply"] and "critical" not in r["reply"].lower()  # not the colour answer


def test_without_a_year_the_latest_year_is_used(client):
    expected = _stored("grain_reserve", "Huye", 2025)
    assert f"{expected:,.1f}" in ask(client, "grain reserve in Huye")["reply"]
    assert "2025" in ask(client, "grain reserve in Huye")["reply"]


def test_years_outside_the_data_say_no_data_found(client):
    r = ask(client, "grain reserve in Musanze in 2026")
    assert r["reply"].startswith("No data found for 2026") and "2000 to 2025" in r["reply"]


def test_seasonal_indicator_gives_each_season_when_no_season_is_named(client):
    r = ask(client, "inorganic fertilizer in Huye in 2021")
    for s in ("A", "B", "C"):
        assert f"Season {s}:" in r["reply"] or f"season {s}" in r["reply"]
    assert "DEMO DATA" in r["reply"]


def test_season_can_be_chosen(client):
    expected = _stored("improved_seeds", "Huye", 2021, "B")
    r = ask(client, "improved seeds in Huye in 2021 season B")
    assert f"{expected:,.1f} % of farmers" in r["reply"] or f"{expected:,.1f}" in r["reply"]
    assert "season B" in r["reply"] and "season A" not in r["reply"]


def test_organic_is_not_confused_with_inorganic(client):
    assert "Organic fertilizer" in ask(client, "organic fertilizer in Huye 2020")["reply"]
    assert "Inorganic" not in ask(client, "organic fertilizer in Huye 2020")["reply"]


def test_indicator_without_a_district_lists_highest_and_lowest(client):
    r = ask(client, "which districts have the most grain reserve in 2015?")
    assert r["intent"] == "indicator" and "Highest:" in r["reply"] and "Lowest:" in r["reply"]


def test_district_status_questions_still_work(client):
    assert ask(client, "Which districts are critical?")["intent"] == "district_status_summary"
    assert ask(client, "Is Musanze in the critical zone?")["intent"] == "district_status"


# ---- product prices over a period, and the graph explanation

def test_period_answer_uses_only_the_chosen_years(client):
    r = ask(client, "irish potatoes in 2010 in Musanze")
    assert r["intent"] == "price_period" and "1 January 2010 to 31 December 2010" in r["reply"]
    assert "Musanze Market" in r["reply"] and "2009" not in r["reply"]


def test_period_outside_the_price_range_says_no_data_found(client):
    r = ask(client, "price of irish potatoes from 2030 to 2031")
    assert r["reply"].startswith("No data found") and "1 January 2000 to 31 August 2026" in r["reply"]


def test_period_partly_outside_is_limited_to_the_covered_dates(client):
    r = ask(client, "irish potatoes in 2026")
    assert "31 August 2026" in r["reply"] and "uses those dates" in r["reply"]


def test_graph_explanation_is_given_without_dates(client):
    r = ask(client, "explain the graph of irish potatoes from-to dates")
    assert r["intent"] == "price_period" and "Each coloured line is one market" in r["reply"]
