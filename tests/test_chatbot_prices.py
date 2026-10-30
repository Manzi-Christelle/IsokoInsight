"""IsokoBot explains price graphs for a chosen period, and refuses questions outside its scope."""
from app.chatbot_prices import parse_period
from datetime import date


def ask(client, text):
    return client.post("/api/chat", json={"message": text}).json()


def test_period_parsing_accepts_the_formats_people_use():
    assert parse_period("from 2010-01-01 to 2015-12-31") == (date(2010, 1, 1), date(2015, 12, 31))
    assert parse_period("from 09/14/2000 to 08/20/2022") == (date(2000, 9, 14), date(2022, 8, 20))
    assert parse_period("from 1 January 2010 to 31 August 2026") == (date(2010, 1, 1), date(2026, 8, 31))
    assert parse_period("between March 2026 and August 2026") == (date(2026, 3, 1), date(2026, 8, 31))
    assert parse_period("in 2010") == (date(2010, 1, 1), date(2010, 12, 31))
    assert parse_period("price of maize in huye") is None


def test_explaining_the_graph_with_dates_gives_the_figures_for_those_dates(client):
    r = ask(client, "explain the graph of irish potatoes from 2010-01-01 to 2015-12-31")
    assert r["intent"] == "price_period"
    assert "Irish potatoes" in r["reply"] and "RWF per kg" in r["reply"]
    assert "1 January 2010 to 31 December 2015" in r["reply"]
    assert "DEMO DATA" in r["reply"]


def test_dates_outside_the_price_range_say_no_data_found(client):
    r = ask(client, "irish potatoes from 1 January 1990 to 1 March 1995")
    assert "No data found" in r["reply"]


def test_questions_outside_the_app_get_the_refusal(client):
    for q in ["Who will win the next football match?", "what is the weather on mars", "tell me a joke"]:
        r = ask(client, q)
        assert r["intent"] == "unknown" and r["reply"] == "can't respond to this!"
