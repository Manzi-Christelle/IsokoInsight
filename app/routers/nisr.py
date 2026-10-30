"""Data for NISR statisticians: full dataset export and statistics generation."""
import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from .. import analytics
from ..db import get_db
from ..districts import district_report
from ..models import OfficialIndicator, OfficialSeries, PriceObservation, User
from ..security import require_permission

router = APIRouter(prefix="/api/nisr", tags=["NISR data"])

DATASET_COLUMNS = ["id", "product", "unit", "market", "district", "price_rwf", "observed_on",
                   "collection_method", "source", "status", "is_synthetic", "created_at"]


@router.get("/dataset.csv")
def full_dataset(db: Session = Depends(get_db), _: User = Depends(require_permission("export_full_dataset"))):
    """Every price record with its verification status. Submitter identities are NOT included."""
    rows = (db.query(PriceObservation)
            .options(joinedload(PriceObservation.product), joinedload(PriceObservation.market),
                     joinedload(PriceObservation.source))
            .order_by(PriceObservation.observed_on, PriceObservation.id).all())
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(DATASET_COLUMNS)
    for o in rows:
        writer.writerow([o.id, o.product.name, o.unit, o.market.name, o.market.district, o.price_rwf,
                         o.observed_on.isoformat(), o.collection_method,
                         o.source.name if o.source else "Contributor submission", o.status,
                         o.is_synthetic, o.created_at.isoformat() if o.created_at else ""])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=nisr_price_dataset.csv"})


@router.get("/statistics")
def statistics(db: Session = Depends(get_db), _: User = Depends(require_permission("view_statistics"))):
    """Statistics generated from VERIFIED records only."""
    obs = (db.query(PriceObservation)
           .options(joinedload(PriceObservation.product), joinedload(PriceObservation.market))
           .filter(PriceObservation.status == "verified").all())
    districts = district_report(db)
    headline = (db.query(OfficialIndicator).filter(OfficialIndicator.name.like("Headline%"))
                .order_by(OfficialIndicator.period.desc()).limit(2).all())
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "Computed from verified records only. Pending and rejected records are excluded. "
                "Records marked is_synthetic are demonstration data, not real prices.",
        "contains_synthetic": any(o.is_synthetic for o in obs),
        "verified_observations": len(obs),
        "products": analytics.summary_by_product(obs),
        "monthly_medians": analytics.monthly_medians(obs),
        "districts": {"as_of": districts["as_of"], "thresholds": districts["thresholds"],
                      "status_counts": {k: sum(1 for d in districts["districts"] if d["status"] == k)
                                        for k in ["critical", "medium", "good", "limited_data", "no_data"]}},
        "official": {"series_count": db.query(OfficialSeries).count(),
                     "headline": [{"name": h.name, "period": h.period.isoformat(), "value": h.value,
                                   "source": h.source.name} for h in headline]},
    }
