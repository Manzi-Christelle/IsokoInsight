from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..districts import district_report
from ..models import Product

router = APIRouter(prefix="/api/districts", tags=["district map"])


@router.get("/status")
def district_status(product_id: int | None = None, db: Session = Depends(get_db)):
    """Colour status for every Rwandan district, from verified prices only.
    Without product_id: overall colours. With product_id: colours and prices for that product only."""
    if product_id is not None and not db.get(Product, product_id):
        raise HTTPException(404, "Unknown product")
    return district_report(db, product_id)
