from datetime import date
from types import SimpleNamespace as NS

from app import analytics
from app.chatbot import answer
from app.districts import load_district_names
from app.db import SessionLocal

from .conftest import login  # noqa: F401  (fixtures come from conftest)


def obs(product_id, product, unit, market_id, market_name, district, price, status="verified",
        when=date(2026, 8, 1), synthetic=False):
    return NS(product_id=product_id, unit=unit, market_id=market_id, price_rwf=price, observed_on=when,
              status=status, is_synthetic=synthetic, product=NS(name=product),
              market=NS(name=market_name, district=district))


DISTRICTS = ["Alpha", "Beta", "Gamma", "Delta", "Empty"]


def test_colour_bands_follow_the_documented_rule():
    # Rice, national median (5 markets) = 1000. Epsilon is +40%.
    rice = [("Alpha", 1000), ("Beta", 1000), ("Gamma", 1000), ("Delta", 1000), ("Epsilon", 1400)]
    # Beans, national median = 500. Beta +10%, Gamma +20%, others 0%.
    beans = [("Alpha", 500), ("Beta", 550), ("Gamma", 600), ("Delta", 500), ("Epsilon", 500)]
    data = [obs(1, "Rice", "kg", i + 1, f"M{i+1}", d, p) for i, (d, p) in enumerate(rice)]
    data += [obs(2, "Beans", "kg", i + 1, f"M{i+1}", d, p) for i, (d, p) in enumerate(beans)]
    rows = {r["name"]: r for r in analytics.district_status(data, DISTRICTS + ["Epsilon"])}
    assert rows["Alpha"]["status"] == "good" and rows["Alpha"]["index_pct"] == 0.0
    assert rows["Beta"]["index_pct"] == 5.0 and rows["Beta"]["status"] == "good"      # exactly 5% is still green
    assert rows["Gamma"]["index_pct"] == 10.0 and rows["Gamma"]["status"] == "medium"
    assert rows["Epsilon"]["index_pct"] == 20.0 and rows["Epsilon"]["status"] == "critical"
    assert rows["Empty"]["status"] == "no_data" and rows["Empty"]["index_pct"] is None


def test_critical_threshold_is_strictly_above_red_limit():
    data = [obs(1, "Rice", "kg", 1, "M1", "Alpha", 1000), obs(1, "Rice", "kg", 2, "M2", "Beta", 1000),
            obs(1, "Rice", "kg", 3, "M3", "Gamma", 1300),
            obs(2, "Beans", "kg", 1, "M1", "Alpha", 500), obs(2, "Beans", "kg", 3, "M3", "Gamma", 500),
            obs(2, "Beans", "kg", 2, "M2", "Beta", 500)]
    rows = {r["name"]: r for r in analytics.district_status(data, DISTRICTS)}
    assert rows["Gamma"]["index_pct"] == 15.0 and rows["Gamma"]["status"] == "medium"
    assert rows["Alpha"]["status"] == "good"


def test_pending_and_single_market_products_are_excluded():
    data = [obs(1, "Rice", "kg", 1, "M1", "Alpha", 1000),
            obs(1, "Rice", "kg", 2, "M2", "Beta", 1000, status="pending"),   # never used
            obs(1, "Rice", "kg", 3, "M3", "Gamma", 1000),
            obs(9, "Oil", "litre", 1, "M1", "Alpha", 5000)]                    # only one market reports oil
    rows = {r["name"]: r for r in analytics.district_status(data, DISTRICTS)}
    assert rows["Beta"]["status"] == "no_data"
    assert rows["Alpha"]["products_used"] == 1 and rows["Alpha"]["status"] == "limited_data"


def test_latest_verified_price_per_market_is_used():
    data = [obs(1, "Rice", "kg", 1, "M1", "Alpha", 900, when=date(2026, 1, 1)),
            obs(1, "Rice", "kg", 1, "M1", "Alpha", 1400, when=date(2026, 6, 1)),   # newer wins
            obs(1, "Rice", "kg", 2, "M2", "Beta", 1000), obs(1, "Rice", "kg", 3, "M3", "Gamma", 1000)]
    rows = {r["name"]: r for r in analytics.district_status(data, DISTRICTS)}
    assert rows["Alpha"]["details"][0]["price_rwf"] == 1400


def test_district_names_come_from_the_boundary_file():
    names = load_district_names()
    assert len(names) == 30 and "Gasabo" in names and "Huye" in names and names == sorted(names)


def test_district_status_endpoint_colours_demo_markets(client):
    res = client.get("/api/districts/status").json()
    assert len(res["districts"]) == 30
    with_data = [d for d in res["districts"] if d["status"] not in ("no_data",)]
    assert len(with_data) == 30                     # every district has verified demo prices, so no grey
    assert all(d["status"] in ("good", "medium", "critical") for d in with_data)
    assert res["contains_synthetic"] is True and res["thresholds"]["red_above_pct"] == 15.0
    assert "not market prices" not in res["note"]  # wording is about colours, not CPI
    assert all(d["status_label"] for d in res["districts"])


def test_map_and_static_assets_are_served(client):
    geo = client.get("/static/data/rwanda_districts.geojson")
    assert geo.status_code == 200 and len(geo.json()["features"]) == 30
    assert "Compare and map" in client.get("/dashboard").text and "chatFab" in client.get("/dashboard").text
    assert "Continue to dashboard" in client.get("/").text  # the root is now the welcome page


def ask(client, text):
    r = client.post("/api/chat", json={"message": text})
    assert r.status_code == 200
    return r.json()


def test_chat_help_and_empty_message(client):
    assert ask(client, "hello")["intent"] == "help"
    assert ask(client, "")["intent"] == "help"


def test_chat_price_answers_use_only_verified_demo_prices(client):
    r = ask(client, "What is the price of maize flour in Huye?")
    assert r["intent"] == "product_price" and "Huye" in r["reply"] and "RWF" in r["reply"]
    assert "DEMO DATA" in r["reply"] and "Verified market prices" in r["sources"]


def test_chat_district_status_and_summary(client):
    one = ask(client, "Is Musanze in the critical zone?")
    assert one["intent"] == "district_status" and one["reply"].startswith(("Yes.", "No.")) and "Musanze" in one["reply"]
    summary = ask(client, "Which districts are red?")
    assert summary["intent"] == "district_status_summary" and "Critical zone (red)" in summary["reply"]
    assert "Gasabo" in summary["reply"] or "Nyarugenge" in summary["reply"] or "Musanze" in summary["reply"]


def test_chat_quotes_official_inflation_and_sources(client):
    inf = ask(client, "What is headline inflation?")
    assert inf["intent"] == "inflation" and "15.9%" in inf["reply"] and "August 2026" in inf["reply"]
    cat = ask(client, "Which categories are rising fastest?")
    assert cat["intent"] == "categories" and "year-on-year" in cat["reply"]
    src = ask(client, "What data is used?")
    assert src["intent"] == "sources" and "SYNTHETIC DEMO" in src["reply"]


def test_chat_methodology_contribute_and_data_status(client):
    assert ask(client, "How are the colours calculated?")["intent"] == "methodology"
    assert ask(client, "How do I submit a price?")["intent"] == "contribute"
    status = ask(client, "Is this real data or demo?")
    assert status["intent"] == "data_status" and "SYNTHETIC" in status["reply"]


def test_chat_unknown_question_gets_the_refusal(client):
    r = ask(client, "Who will win the next football match?")
    assert r["intent"] == "unknown" and r["reply"] == "can't respond to this!"


def test_chat_never_quotes_pending_submissions(client, contributor):
    from datetime import date as d
    payload = {"product_id": 1, "market_id": 1, "price_rwf": 123456, "unit": "kg", "observed_on": d.today().isoformat()}
    assert client.post("/api/prices", json=payload, headers=contributor).status_code == 201
    assert "123,456" not in ask(client, "price of irish potatoes in kimironko")["reply"]


def test_chat_message_length_limited(client):
    assert client.post("/api/chat", json={"message": "x" * 501}).status_code == 422


def test_product_filter_recolours_by_one_product(client):
    res = client.get("/api/districts/status?product_id=1").json()
    assert res["product_id"] == 1
    with_data = [d for d in res["districts"] if d["status"] != "no_data"]
    assert len(with_data) == 30
    for d in with_data:
        assert d["products_used"] == 1 and d["status"] in ("good", "medium", "critical")
        assert all(x["product"] == "Irish potatoes" and x["market"] for x in d["details"])
    assert client.get("/api/districts/status?product_id=999").status_code == 404


def test_overall_colours_unchanged_without_product(client):
    res = client.get("/api/districts/status").json()
    assert res["product_id"] is None
    assert all(d["products_used"] in (0,) or d["products_used"] >= 2 for d in res["districts"] if d["status"] != "no_data")
