import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from .. import analytics
from ..config import settings
from ..db import get_db
from ..models import Alert, DataSource, Market, PriceObservation, Product, User
from ..price_map import district_prices
from ..districts import load_district_names
from ..schemas import PriceIn
from ..security import require_permission

router = APIRouter(prefix="/api", tags=["prices"])


def obs_to_dict(o: PriceObservation) -> dict:
    return {
        "id": o.id, "product": o.product.name, "product_id": o.product_id,
        "market": o.market.name, "district": o.market.district, "market_id": o.market_id,
        "price_rwf": o.price_rwf, "unit": o.unit, "observed_on": o.observed_on.isoformat(),
        "collection_method": o.collection_method,
        "source": o.source.name if o.source else "Contributor submission",
        "status": o.status, "is_synthetic": o.is_synthetic,
    }


@router.get("/products")
def products(db: Session = Depends(get_db)):
    return [{"id": p.id, "name": p.name, "category": p.category, "standard_unit": p.standard_unit}
            for p in db.query(Product).order_by(Product.name)]


@router.get("/markets")
def markets(db: Session = Depends(get_db)):
    return [{"id": m.id, "name": m.name, "district": m.district}
            for m in db.query(Market).order_by(Market.district, Market.name)]


@router.get("/sources")
def sources(db: Session = Depends(get_db)):
    """Source register: every dataset used, with provenance."""
    return [{"id": s.id, "name": s.name, "publisher": s.publisher, "url": s.url,
             "description": s.description, "period": s.period,
             "downloaded_on": s.downloaded_on.isoformat() if s.downloaded_on else None,
             "transformations": s.transformations, "is_synthetic": s.is_synthetic}
            for s in db.query(DataSource).order_by(DataSource.id)]


def _filtered(db, product_id, market_id, unit, date_from, date_to):
    q = (db.query(PriceObservation)
         .options(joinedload(PriceObservation.product), joinedload(PriceObservation.market),
                  joinedload(PriceObservation.source))
         .filter(PriceObservation.status == "verified"))  # public endpoints show verified only
    if product_id:
        q = q.filter(PriceObservation.product_id == product_id)
    if market_id:
        q = q.filter(PriceObservation.market_id == market_id)
    if unit:
        q = q.filter(PriceObservation.unit == unit)
    if date_from:
        q = q.filter(PriceObservation.observed_on >= date_from)
    if date_to:
        q = q.filter(PriceObservation.observed_on <= date_to)
    return q


@router.get("/prices")
def list_prices(product_id: int | None = None, market_id: int | None = None, unit: str | None = None,
                date_from: date | None = None, date_to: date | None = None,
                limit: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db)):
    q = _filtered(db, product_id, market_id, unit, date_from, date_to)
    rows = q.order_by(PriceObservation.observed_on.desc(), PriceObservation.id.desc()).limit(limit).all()
    return [obs_to_dict(o) for o in rows]


@router.get("/prices/compare")
def compare(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Unknown product")
    obs = _filtered(db, product_id, None, None, None, None).all()
    groups = analytics.compare_markets(obs)
    return {"product": product.name, "groups_by_unit": groups,
            "note": "Latest verified price per market. Different units are never compared with "
                    "each other. These are local market observations, not CPI statistics.",
            "contains_synthetic": any(r["is_synthetic"] for g in groups.values() for r in g["rows"])}


@router.get("/prices/district-map")
def price_by_district(product_id: int, db: Session = Depends(get_db)):
    """One product's verified prices compared across the 30 districts (average of its markets)."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Unknown product")
    obs = _filtered(db, product_id, None, None, None, None).all()
    result = district_prices(obs, load_district_names())
    return {"product": product.name, "unit": product.standard_unit,
            "note": "Average of the latest verified price at each market in the district. Districts without "
                    "a market that has verified this product are left uncoloured. These are local market "
                    "observations, not CPI statistics.", **result}


@router.get("/prices/coverage")
def price_coverage():
    """The dates the price search covers. The screen uses this to limit the date pickers."""
    return {"start": settings.price_range_start.isoformat(), "end": settings.price_range_end.isoformat(),
            "contains_synthetic": True,
            "note": "Demonstration prices are monthly from January 2000 to August 2026. "
                    "They are SYNTHETIC and are labelled on every screen."}


@router.get("/prices/history")
def history(product_id: int, market_id: int | None = None, unit: str | None = None,
            date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db)):
    """Verified prices for one product, grouped by market, for the chosen dates (same filters as the table)."""
    obs = _filtered(db, product_id, market_id, unit, date_from, date_to).order_by(PriceObservation.observed_on).all()
    series: dict[str, list] = {}
    for o in obs:
        series.setdefault(f"{o.market.name} ({o.unit})", []).append(
            {"date": o.observed_on.isoformat(), "price_rwf": o.price_rwf})
    return series


@router.get("/prices/export.csv")
def export_csv(product_id: int | None = None, market_id: int | None = None, unit: str | None = None,
               date_from: date | None = None, date_to: date | None = None,
               db: Session = Depends(get_db), _: User = Depends(require_permission("download_verified_csv"))):
    rows = [obs_to_dict(o) for o in _filtered(db, product_id, market_id, unit, date_from, date_to)
            .order_by(PriceObservation.observed_on.desc()).limit(10000)]
    buf = io.StringIO()
    cols = ["id", "product", "market", "district", "price_rwf", "unit", "observed_on", "source",
            "status", "is_synthetic"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=isoko_prices.csv"})


@router.post("/prices", status_code=201)
def submit_price(body: PriceIn, db: Session = Depends(get_db),
                 user: User = Depends(require_permission("submit_price"))):
    """Contributors submit observations; they start as PENDING and are never shown as verified."""
    product = db.get(Product, body.product_id)
    market = db.get(Market, body.market_id)
    if not product or not market:
        raise HTTPException(422, "Unknown product or market")
    if body.unit != product.standard_unit:
        raise HTTPException(422, f"Unit for {product.name} must be '{product.standard_unit}'. "
                                 "Convert before submitting so prices stay comparable.")
    if body.source_id and not db.get(DataSource, body.source_id):
        raise HTTPException(422, "Unknown source")
    obs = PriceObservation(product_id=product.id, market_id=market.id, price_rwf=body.price_rwf,
                           unit=body.unit, observed_on=body.observed_on,
                           collection_method=body.collection_method, source_id=body.source_id,
                           submitted_by=user.id, status="pending", is_synthetic=False)
    db.add(obs)
    db.flush()
    # Review flag if far from the last verified price for the same product/market/unit.
    prev = (db.query(PriceObservation)
            .filter_by(product_id=product.id, market_id=market.id, unit=body.unit, status="verified")
            .filter(PriceObservation.observed_on <= body.observed_on)
            .order_by(PriceObservation.observed_on.desc()).first())
    flagged = None
    if prev:
        change = analytics.pct_change(body.price_rwf, prev.price_rwf)
        if change is not None and abs(change) >= settings.price_change_threshold_pct:
            flagged = round(change, 1)
            db.add(Alert(kind="price_observation", ref=str(obs.id), period=body.observed_on,
                         change_pct=flagged,
                         message=f"{product.name} at {market.name}: {body.price_rwf} RWF is {flagged:+}% "
                                 f"versus the last verified {prev.price_rwf} RWF. Please review; "
                                 "this does not mean a shortage or error exists."))
    db.commit()
    return {"id": obs.id, "status": obs.status, "flagged_for_review": flagged is not None,
            "message": "Submitted. It will appear publicly after an administrator verifies it."}


@router.get("/me/submissions")
def my_submissions(db: Session = Depends(get_db), user: User = Depends(require_permission("view_own_submissions"))):
    """The signed-in person's own submissions and their status (pending, verified or rejected)."""
    rows = (db.query(PriceObservation)
            .options(joinedload(PriceObservation.product), joinedload(PriceObservation.market),
                     joinedload(PriceObservation.source))
            .filter(PriceObservation.submitted_by == user.id)
            .order_by(PriceObservation.created_at.desc()).limit(500).all())
    return [obs_to_dict(o) for o in rows]
