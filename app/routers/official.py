from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import analytics
from ..config import settings
from ..db import get_db
from ..models import OfficialIndicator, OfficialSeries, OfficialValue

router = APIRouter(prefix="/api/official", tags=["official statistics"])

NOTE = ("Official CPI statistics from the National Institute of Statistics of Rwanda (NISR). "
        "National indices - not market prices for individual products.")


def _points(db, series_id):
    return [(v.period, v.index_value) for v in
            db.query(OfficialValue).filter_by(series_id=series_id).order_by(OfficialValue.period)]


@router.get("/series")
def list_series(db: Session = Depends(get_db)):
    out = []
    for s in db.query(OfficialSeries).order_by(OfficialSeries.group, OfficialSeries.name):
        data = analytics.add_changes(_points(db, s.id))
        if not data:
            continue
        last = data[-1]
        out.append({"code": s.code, "name": s.name, "group": s.group, "weight": s.weight,
                    "latest_period": last["period"], "latest_index": last["value"],
                    "mom_pct": last["mom_pct"], "yoy_pct": last["yoy_pct"],
                    "source": s.source.name, "is_synthetic": s.source.is_synthetic})
    return {"note": NOTE, "series": out}


@router.get("/series/{code}")
def series_detail(code: str, db: Session = Depends(get_db)):
    s = db.query(OfficialSeries).filter_by(code=code).one_or_none()
    if not s:
        raise HTTPException(404, "Unknown series")
    pts = _points(db, s.id)
    anomalies = analytics.detect_series_anomalies(pts, settings.cpi_mom_threshold_pct)
    return {"note": NOTE, "code": s.code, "name": s.name, "group": s.group,
            "source": {"name": s.source.name, "publisher": s.source.publisher, "url": s.source.url,
                       "is_synthetic": s.source.is_synthetic},
            "data": analytics.add_changes(pts),
            "review_flags": [{**a, "period": a["period"].isoformat(),
                              "message": "Flagged for review - verify against the NISR release; "
                                         "this is not a conclusion about the cause."} for a in anomalies]}


@router.get("/indicators")
def indicators(db: Session = Depends(get_db)):
    rows = db.query(OfficialIndicator).order_by(OfficialIndicator.period.desc(), OfficialIndicator.name)
    return [{"name": i.name, "period": i.period.isoformat(), "value": i.value, "unit": i.unit,
             "source": i.source.name, "url": i.source.url} for i in rows]
