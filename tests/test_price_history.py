"""The price search covers January 2000 to August 2026, and the history chart follows the same dates as the table."""
from datetime import date

from app.config import settings


def _beef(client):
    return next(p["id"] for p in client.get("/api/products").json() if p["name"] == "Beef")


def test_coverage_endpoint_states_the_range(client):
    cov = client.get("/api/prices/coverage").json()
    assert cov["start"] == "2000-01-01" and cov["end"] == "2026-08-31"
    assert cov["contains_synthetic"] is True and "SYNTHETIC" in cov["note"]
    assert settings.price_range_start == date(2000, 1, 1) and settings.price_range_end == date(2026, 8, 31)


def test_demo_prices_cover_every_month_from_2000_to_august_2026(client):
    from app.db import SessionLocal
    from app.models import PriceObservation
    from sqlalchemy import func
    with SessionLocal() as db:
        first, last = db.query(func.min(PriceObservation.observed_on), func.max(PriceObservation.observed_on)).filter_by(
            is_synthetic=True).one()
        months = db.query(func.count(func.distinct(PriceObservation.observed_on))).filter_by(is_synthetic=True).scalar()
    assert first == date(2000, 1, 15) and last == date(2026, 8, 15)
    assert months == 320  # January 2000 to August 2026, one date per month


def test_history_respects_the_date_range(client):
    pid = _beef(client)
    early = client.get("/api/prices/history", params={"product_id": pid,
                       "date_from": "2000-09-01", "date_to": "2000-09-30"}).json()
    assert early and all(len(pts) == 1 and pts[0]["date"] == "2000-09-15" for pts in early.values())
    later = client.get("/api/prices/history", params={"product_id": pid,
                       "date_from": "2026-09-01", "date_to": "2026-12-31"}).json()
    assert later == {}  # nothing after August 2026 in the demo data
    inside = client.get("/api/prices/history", params={"product_id": pid,
                        "date_from": "2026-05-01", "date_to": "2026-06-30"}).json()
    dates = [p["date"] for pts in inside.values() for p in pts]
    assert dates and min(dates) >= "2026-05-01" and max(dates) <= "2026-06-30"


def test_prices_for_one_market_show_the_long_run_trend(client):
    pid = _beef(client)
    h = client.get("/api/prices/history", params={"product_id": pid}).json()
    kimironko = next(v for k, v in h.items() if k.startswith("Kimironko"))
    assert len(kimironko) == 320
    assert kimironko[-1]["price_rwf"] > 2 * kimironko[0]["price_rwf"]  # prices rise over the 26 years
