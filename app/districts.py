"""Shared district report used by the district map API and by the chatbot."""
import json
from pathlib import Path

from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from . import analytics
from .config import settings
from .models import PriceObservation, Product
from .reference import CORE_PRODUCT_NAMES

GEOJSON_PATH = Path(__file__).parent / "static" / "data" / "rwanda_districts.geojson"

STATUS_LABELS = {
    "critical": "Critical zone (red)",
    "medium": "Medium (yellow)",
    "good": "Good (green)",
    "limited_data": "Limited data (grey)",
    "no_data": "No verified data (grey)",
}


def load_district_names() -> list[str]:
    data = json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))
    return [f["properties"]["name"] for f in data["features"]]


def latest_verified_observations(db: Session, product_id: int | None = None) -> list:
    """The latest verified price for each (product, unit, market), picked in the database.

    Loading every verified observation and choosing the latest in Python is slow (over 100,000 rows).
    Here the database returns only the newest date per (product, unit, market), which is at most a few hundred rows.
    """
    base = (db.query(PriceObservation.product_id, PriceObservation.unit, PriceObservation.market_id,
                     func.max(PriceObservation.observed_on).label("latest"))
            .filter(PriceObservation.status == "verified"))
    if product_id:
        base = base.filter(PriceObservation.product_id == product_id)
    else:
        # Overall colours use the six staple products only, so added products do not change them.
        base = (base.join(Product, Product.id == PriceObservation.product_id)
                .filter(Product.name.in_(CORE_PRODUCT_NAMES)))
    newest = base.group_by(PriceObservation.product_id, PriceObservation.unit,
                           PriceObservation.market_id).subquery()
    q = (db.query(PriceObservation)
         .join(newest, and_(PriceObservation.product_id == newest.c.product_id,
                            PriceObservation.unit == newest.c.unit,
                            PriceObservation.market_id == newest.c.market_id,
                            PriceObservation.observed_on == newest.c.latest))
         .options(joinedload(PriceObservation.product), joinedload(PriceObservation.market))
         .filter(PriceObservation.status == "verified"))
    return q.all()


def district_report(db: Session, product_id: int | None = None) -> dict:
    """Overall colours (all products), or colours for one product when product_id is given.

    For one product the comparison is a single price per market, so one market is enough to colour a district.
    """
    obs = latest_verified_observations(db, product_id)
    min_products = 1 if product_id else settings.district_min_products
    rows = analytics.district_status(obs, load_district_names(),
                                     yellow_pct=settings.district_yellow_pct,
                                     red_pct=settings.district_red_pct,
                                     min_products=min_products)
    for r in rows:
        r["status_label"] = STATUS_LABELS[r["status"]]
    dates = [r["latest_date"] for r in rows if r["latest_date"]]
    return {
        "as_of": max(dates) if dates else None,
        "product_id": product_id,
        "contains_synthetic": any(r["contains_synthetic"] for r in rows),
        "thresholds": {"yellow_above_pct": settings.district_yellow_pct,
                       "red_above_pct": settings.district_red_pct,
                       "min_products": settings.district_min_products},
        "note": ("Colours compare verified local market prices with the national median for the "
                 "same product and unit. They flag where prices are high and need attention; they do "
                 "not measure living standards or prove a shortage. Market prices are not NISR CPI."
                 + ("" if product_id else " Overall colours use the six staple products only.")),
        "districts": rows,
    }