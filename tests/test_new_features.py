"""Tests for the welcome page, the weather and climate tab, the price map and the added products.

Expected values were worked out by hand from the rules in app/climate.py and app/price_map.py.
These features must not change the existing figures: the staple-product district colours are checked too.
"""
import random
from types import SimpleNamespace as NS

import pytest
from pytest import approx

from app import climate
from app.db import SessionLocal
from app.models import ClimateObservation, PriceObservation
from app.price_map import district_prices
from app.seed import purge_demo, seed_demo


def _product_id(client, name):
    return next(p["id"] for p in client.get("/api/products").json() if p["name"] == name)


# ---- Welcome page and images

def test_welcome_page_links_to_dashboard_and_serves_all_images(client):
    page = client.get("/").text
    assert "Welcome to IsokoInsight Rwanda" in page and 'href="/dashboard"' in page
    assert "Continue to dashboard" in page
    assert page.count('<figure class="slide') == 7
    for name in ["01-dairy-milk-collection.jpg", "02-fertiliser-application.jpg", "03-farmer-mobile-phone.jpg",
                 "04-market-produce.jpg", "05-tea-harvest.jpg", "06-drought-field.jpg", "07-cash-and-prices.jpg"]:
        r = client.get("/static/img/" + name)
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg", name


def test_dashboard_still_serves_the_main_page_with_new_tabs(client):
    page = client.get("/dashboard").text
    assert "Compare and map" in page and "chatFab" in page and "Indicators map" in page
    assert 'data-tab="climate"' in page and 'id="pmProduct"' in page
    assert "/static/climate.js" in page and "/static/market-map.js" in page


# ---- Impact rules, by hand

@pytest.mark.parametrize("pct, key", [(-25, "severe_dry"), (-20, "severe_dry"), (-15, "dry"), (0, "normal"),
                                      (9.9, "normal"), (10, "wet"), (19.9, "wet"), (20, "very_wet")])
def test_impact_classes_follow_the_bands(pct, key):
    assert climate.impact_class(pct) == key


def test_heat_sentence_is_added_only_when_temperature_is_well_above_normal():
    base = climate.impact_text("normal", 0.3)
    assert "heat stress" not in base
    assert "heat stress" in climate.impact_text("normal", 0.8)


def test_district_summary_by_hand():
    # Normal: 1200 mm a year, 20 C. This year: 100 mm every month = 1200 mm (0%) and 21 C (+1 C).
    months = {m: (100.0, 21.0) for m in range(1, 13)}
    s = climate.district_summary(months, 1200.0, 20.0)
    assert s["rain_vs_normal_pct"] == 0.0 and s["impact_class"] == "normal"
    assert s["temp_vs_normal_c"] == 1.0 and "heat stress" in s["impact_text"]
    # 1000 mm is 16.7% below normal, which is "dry".
    dry = climate.district_summary({m: (1000 / 12, 20.0) for m in range(1, 13)}, 1200.0, 20.0)
    assert dry["rain_vs_normal_pct"] == approx(-16.7, abs=0.05) and dry["impact_class"] == "dry"


def test_simulation_has_every_district_month_and_a_drought_year():
    rows = climate.simulate(random.Random(2028))
    assert len(rows) == 30 * 10 * 12
    assert len(set((r[0], r[1], r[2]) for r in rows)) == len(rows)  # no duplicate months
    assert rows == climate.simulate(random.Random(2028))            # same seed, same data
    east_2022 = [r for r in rows if r[0] in ("Kayonza", "Kirehe") and r[1] == 2022]
    east_other = [r for r in rows if r[0] in ("Kayonza", "Kirehe") and r[1] == 2019]
    assert sum(r[3] for r in east_2022) < 0.9 * sum(r[3] for r in east_other)  # 2022 was a dry year in the east


# ---- Climate endpoints

def test_climate_years_and_status_shape(client):
    years = client.get("/api/climate/years").json()
    assert years["years"] == list(range(2016, 2026)) and years["baseline_years"] == years["years"]
    st = client.get("/api/climate/status", params={"year": 2022}).json()
    assert len(st["districts"]) == 30 and st["contains_synthetic"] is True
    assert len(st["legend"]["rain"]) == 5 and len(st["legend"]["temp"]) == 4
    assert len(st["impact_guide"]) == 5 and "SYNTHETIC" in st["note"]
    kayonza = next(d for d in st["districts"] if d["name"] == "Kayonza")
    assert kayonza["data_available"] is True and kayonza["rain_vs_normal_pct"] < -10   # the east dry year
    assert kayonza["impact_class"] in ("dry", "severe_dry")


def test_climate_status_refuses_years_outside_the_data(client):
    assert client.get("/api/climate/status", params={"year": 1990}).status_code == 422
    assert client.get("/api/climate/district", params={"district": "Atlantis", "year": 2020}).status_code == 404
    assert client.get("/api/climate/district", params={"district": "Gasabo", "year": 2030}).status_code == 422


def test_district_detail_matches_the_status_row(client):
    st = client.get("/api/climate/status", params={"year": 2020}).json()
    row = next(d for d in st["districts"] if d["name"] == "Musanze")
    det = client.get("/api/climate/district", params={"district": "Musanze", "year": 2020}).json()
    assert len(det["months"]) == 12
    assert det["summary"]["rain_vs_normal_pct"] == row["rain_vs_normal_pct"]
    assert det["summary"]["impact_class"] == row["impact_class"]
    # The 2020 north event was wet, so the annual total should be above normal.
    assert row["rain_vs_normal_pct"] > 5
    assert sum(m["rain_mm"] for m in det["months"]) == approx(row["rain_mm"], abs=1.0)  # monthly values are rounded


# ---- Price by district: pure logic, by hand

def _obs(market_id, market_name, district, price, day, status="verified", synthetic=True):
    from datetime import date
    return NS(market_id=market_id, market=NS(name=market_name, district=district), unit="kg",
               price_rwf=price, observed_on=date(2026, 6, day), status=status, is_synthetic=synthetic)


def test_district_prices_average_bands_and_gaps_by_hand():
    obs = [
        _obs(1, "A market", "Alpha", 1000, 1),
        _obs(2, "B market", "Alpha", 1200, 2),
        _obs(1, "A market", "Alpha", 1100, 10),         # newer price at A replaces 1000: Alpha = (1100 + 1200) / 2
        _obs(3, "C market", "Beta", 2000, 5),           # Beta = 2000
        _obs(4, "D market", "Gamma", 1500, 5, status="pending"),   # pending: ignored
    ]
    res = district_prices(obs, ["Alpha", "Beta", "Gamma", "Delta"])
    by = {d["name"]: d for d in res["districts"]}
    assert by["Alpha"]["average_rwf"] == 1150 and by["Alpha"]["markets_count"] == 2
    assert by["Beta"]["average_rwf"] == 2000
    assert by["Gamma"]["average_rwf"] is None and by["Delta"]["average_rwf"] is None
    assert res["cheapest_district"] == "Alpha" and res["highest_district"] == "Beta"
    assert res["spread_pct"] == approx(73.9, abs=0.05)               # (2000 - 1150) / 1150
    assert res["band_edges_rwf"] == [1150, 1320, 1490, 1660, 1830, 2000]  # five equal steps of 170
    assert by["Alpha"]["band"] == 0 and by["Beta"]["band"] == 4
    assert by["Alpha"]["vs_cheapest_pct"] == 0 and by["Beta"]["vs_cheapest_pct"] == approx(73.9, abs=0.05)


def test_district_prices_with_one_district_uses_the_middle_band():
    res = district_prices([_obs(1, "A market", "Alpha", 900, 1)], ["Alpha", "Beta"])
    assert res["districts"][0]["band"] == 2 and res["spread_pct"] == 0.0


# ---- Price by district: endpoint

def test_price_map_endpoint_covers_added_and_original_products(client):
    beef = _product_id(client, "Beef")
    res = client.get("/api/prices/district-map", params={"product_id": beef}).json()
    assert len(res["districts"]) == 30 and res["unit"] == "kg" and res["contains_synthetic"] is True
    assert all(d["average_rwf"] is not None for d in res["districts"])   # every district is coloured
    assert res["districts_with_prices"] == 30
    # Staple products are also priced at the coverage markets now, so every district has prices for them too.
    potatoes = _product_id(client, "Irish potatoes")
    res_p = client.get("/api/prices/district-map", params={"product_id": potatoes}).json()
    assert res_p["districts_with_prices"] == 30
    assert client.get("/api/prices/district-map", params={"product_id": 999}).status_code == 404


# ---- Staple colours and original figures are unchanged

def test_overall_district_colours_still_use_only_the_six_staples(client):
    overall = {d["name"]: d for d in client.get("/api/districts/status").json()["districts"]}
    assert overall["Gasabo"]["products_used"] == 6          # not 14: added products are not counted
    for added in ["Rubavu", "Nyagatare", "Muhanga", "Rusizi"]:
        assert overall[added]["products_used"] == 6         # staples are priced at these markets too
    assert "Overall colours use the six staple products only." in client.get("/api/districts/status").json()["note"]


def test_every_market_prices_the_staples_for_full_district_coverage(client):
    potatoes = _product_id(client, "Irish potatoes")
    rows = client.get("/api/prices", params={"product_id": potatoes, "limit": 1000}).json()
    assert len({r["district"] for r in rows}) == 30


# ---- Seeding and purge

def test_reseeding_does_not_duplicate_demo_rows(client):
    with SessionLocal() as db:
        before = (db.query(ClimateObservation).count(), db.query(PriceObservation).count())
        seed_demo(db)
        after = (db.query(ClimateObservation).count(), db.query(PriceObservation).count())
    assert before == after == (30 * 10 * 12, before[1])


def test_purge_removes_added_demo_climate_and_prices(client):
    with SessionLocal() as db:
        purge_demo(db)
    with SessionLocal() as db:
        assert db.query(ClimateObservation).count() == 0
    st = client.get("/api/climate/status", params={"year": 2022}).json()
    assert all(d["data_available"] is False for d in st["districts"])
    assert client.get("/api/prices/district-map", params={"product_id": _product_id(client, "Beef")}).json()[
        "districts_with_prices"] == 0
