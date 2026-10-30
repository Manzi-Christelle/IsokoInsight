from statistics import mean

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from .. import climate
from ..db import get_db
from ..districts import load_district_names
from ..models import ClimateObservation

router = APIRouter(prefix="/api/climate", tags=["weather and climate"])


def _load(db: Session):
    rows = db.query(ClimateObservation).options(joinedload(ClimateObservation.source)).all()
    table = climate.build_table(rows)
    synthetic = any(r.source.is_synthetic for r in rows) if rows else False
    return table, synthetic


@router.get("/years")
def years():
    return {"years": climate.CLIMATE_YEARS, "baseline_years": climate.BASELINE_YEARS,
            "note": climate.NOTE, "contains_synthetic": True}


@router.get("/status")
def status(year: int = Query(climate.CLIMATE_YEARS[-1]), db: Session = Depends(get_db)):
    """Every district for one year: rainfall and temperature against normal, and the farming impact."""
    if year not in climate.CLIMATE_YEARS:
        raise HTTPException(422, f"Year must be one of {climate.CLIMATE_YEARS[0]} to {climate.CLIMATE_YEARS[-1]}")
    table, synthetic = _load(db)
    rows = []
    for name in load_district_names():
        summary = climate.district_year(table, name, year)
        rows.append({"name": name, "province": climate.DISTRICT_PROVINCE.get(name),
                     "data_available": summary is not None, **(summary or {})})
    return {"year": year, "note": climate.NOTE, "impact_note": climate.IMPACT_NOTE,
            "contains_synthetic": synthetic, "baseline_years": climate.BASELINE_YEARS,
            "legend": {"rain": climate.legend_for("rain"), "temp": climate.legend_for("temp")},
            "temp_bounds": climate.TEMP_BOUNDS, "impact_bounds": climate.IMPACT_BOUNDS,
            "impact_guide": [{"key": k, "label": label, "colour": c, "text": t}
                             for k, label, c, t in climate.IMPACT_CLASSES],
            "districts": rows}


@router.get("/district")
def district_detail(district: str, year: int = Query(climate.CLIMATE_YEARS[-1]),
                    db: Session = Depends(get_db)):
    """One district's monthly rainfall and temperature for a year, against its normal for each month."""
    if district not in load_district_names():
        raise HTTPException(404, "Unknown district")
    if year not in climate.CLIMATE_YEARS:
        raise HTTPException(422, f"Year must be one of {climate.CLIMATE_YEARS[0]} to {climate.CLIMATE_YEARS[-1]}")
    table, synthetic = _load(db)
    summary = climate.district_year(table, district, year)
    if summary is None:
        raise HTTPException(404, "No climate data for this district and year")
    years = table[district]
    months = []
    for m in range(1, 13):
        base = [years[y][m] for y in climate.BASELINE_YEARS if y in years and m in years[y]]
        this = years[year][m]
        months.append({"month": m, "rain_mm": this[0], "rain_normal_mm": round(mean(b[0] for b in base), 1),
                       "temp_c": this[1], "temp_normal_c": round(mean(b[1] for b in base), 1)})
    return {"district": district, "province": climate.DISTRICT_PROVINCE.get(district), "year": year,
            "note": climate.NOTE, "impact_note": climate.IMPACT_NOTE, "contains_synthetic": synthetic,
            "summary": summary, "months": months}
