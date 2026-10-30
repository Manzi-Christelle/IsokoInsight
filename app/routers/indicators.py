"""District indicators: values, year-on-year changes, national summaries and the food security score.

All figures here come from SYNTHETIC demonstration workbooks (except the labelled national input
figures). Every response carries a flag or note so a screen cannot show them without a label.
"""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import indicator_calc
from ..db import get_db
from ..districts import load_district_names
from ..indicator_data import load_panel
from ..indicators import (ALL_ITEMS, BY_KEY, FOOD_SECURITY, GROUP_TITLES, NATIONAL, PILLAR_LABELS,
                          SCORE_PILLARS, SOURCE_NAMES)

router = APIRouter(prefix="/api/indicators", tags=["district indicators"])

NOTE = ("SYNTHETIC DEMONSTRATION DATA. These values are randomly generated for the prototype and are NOT "
        "NISR or census statistics. Do not use them for analysis or reporting.")
SCORE_NOTE = ("The food security score is a relative index for illustration. It is the average of three "
              "pillars, each scaled 0-100 between the lowest and highest district-year in 2000-2025. "
              "It does not measure hunger or nutrition, and it is not an official NISR measure.")
DEFAULT_YEAR = 2025
DEFAULT_SEASON = "A"


def _item(key: str):
    if key not in BY_KEY:
        raise HTTPException(404, "Unknown indicator")
    return BY_KEY[key]


def _season(item, season: str) -> str:
    return season if item.seasonal else ""


def _check_district(name: str) -> str:
    if name != NATIONAL and name not in set(load_district_names()):
        raise HTTPException(404, "Unknown district")
    return name


@router.get("/catalog")
def catalog(db: Session = Depends(get_db)):
    """Every indicator, with the years and seasons it covers and whether it is synthetic."""
    panel = load_panel(db)
    out = []
    for it in ALL_ITEMS:
        vals = panel.series(it.key)
        years = sorted({y for (d, y, s) in vals if d != NATIONAL})
        out.append({"key": it.key, "label": it.label, "group": it.group,
                    "group_title": GROUP_TITLES[it.group], "unit": it.unit, "seasonal": it.seasonal,
                    "seasons": sorted({s for (_, _, s) in vals if s}),
                    "first_year": years[0] if years else None, "last_year": years[-1] if years else None,
                    "description": it.description, "synthetic": panel.synthetic.get(it.key, False),
                    "source": (SOURCE_NAMES.get(it.group) if it.key != FOOD_SECURITY
                               else "Calculated from the market access, grain and livestock sources")})
    return {"note": NOTE, "items": out}


@router.get("/map")
def indicator_map(indicator: str,
                  year: int = Query(DEFAULT_YEAR, ge=2000, le=2026),
                  season: str = Query(DEFAULT_SEASON, pattern="^[ABC]$"),
                  db: Session = Depends(get_db)):
    """Every district's value for one indicator in one year (and season, where the survey has them),
    with the change from the year before."""
    item = _item(indicator)
    panel = load_panel(db)
    s = _season(item, season)
    values = panel.series(item.key)
    districts = load_district_names()
    rows = indicator_calc.snapshot_rows(values, districts, year, s)
    shown = [r["value"] for r in rows if r["value"] is not None]
    return {
        "indicator": item.key, "label": item.label, "unit": item.unit, "group": item.group,
        "group_title": GROUP_TITLES[item.group], "description": item.description,
        "year": year, "season": s or None,
        "years": sorted({y for (d, y, ss) in values if ss == s and d != NATIONAL}),
        "seasons": sorted({ss for (_, _, ss) in values if ss}) if item.seasonal else [],
        "scale": {"min": min(shown) if shown else None, "max": max(shown) if shown else None},
        "districts": rows,
        "national": indicator_calc.national_summary(values, districts, year, s),
        "national_reported": values.get((NATIONAL, year, s)),
        "national_reported_prev": values.get((NATIONAL, year - 1, s)),
        "synthetic": panel.synthetic.get(item.key, False),
        "note": SCORE_NOTE if item.key == FOOD_SECURITY else NOTE,
    }


@router.get("/series")
def indicator_series(indicator: str, district: str, db: Session = Depends(get_db)):
    """Every year (and season) of one indicator for one district, with the change each year."""
    item = _item(indicator)
    _check_district(district)
    panel = load_panel(db)
    values = panel.series(item.key)
    points = []
    for y, s in sorted({(y, s) for (d, y, s) in values if d == district}):
        cur = values[(district, y, s)]
        prev = values.get((district, y - 1, s))
        abs_change, pct = indicator_calc.change(cur, prev)
        points.append({"year": y, "season": s or None, "value": round(cur, 2),
                       "prev_value": None if prev is None else round(prev, 2),
                       "change_abs": abs_change, "change_pct": pct})
    return {"indicator": item.key, "label": item.label, "unit": item.unit, "district": district,
            "synthetic": panel.synthetic.get(item.key, False), "points": points}


@router.get("/district")
def district_items(district: str,
                   year: int = Query(DEFAULT_YEAR, ge=2000, le=2026),
                   season: str = Query(DEFAULT_SEASON, pattern="^[ABC]$"),
                   db: Session = Depends(get_db)):
    """Every indicator for one district in one year, each with its value and change from the year before."""
    _check_district(district)
    panel = load_panel(db)
    items = []
    for it in ALL_ITEMS:
        s = _season(it, season)
        values = panel.series(it.key)
        cur = values.get((district, year, s))
        prev = values.get((district, year - 1, s))
        abs_change, pct = indicator_calc.change(cur, prev)
        items.append({"key": it.key, "label": it.label, "group": it.group,
                      "group_title": GROUP_TITLES[it.group], "unit": it.unit,
                      "season": s or None,
                      "value": None if cur is None else round(cur, 2),
                      "prev_value": None if prev is None else round(prev, 2),
                      "change_abs": abs_change, "change_pct": pct,
                      "synthetic": panel.synthetic.get(it.key, False)})
    return {"district": district, "year": year, "season": season, "items": items, "note": NOTE}


@router.get("/summary")
def national_summary(year: int = Query(DEFAULT_YEAR, ge=2000, le=2026),
                     season: str = Query(DEFAULT_SEASON, pattern="^[ABC]$"),
                     db: Session = Depends(get_db)):
    """National average of every indicator for one year, with the average change from the year before."""
    panel = load_panel(db)
    districts = load_district_names()
    out = []
    for it in ALL_ITEMS:
        s = _season(it, season)
        values = panel.series(it.key)
        nat = indicator_calc.national_summary(values, districts, year, s)
        cur_rep = values.get((NATIONAL, year, s))
        prev_rep = values.get((NATIONAL, year - 1, s))
        out.append({"key": it.key, "label": it.label, "group": it.group,
                    "group_title": GROUP_TITLES[it.group], "unit": it.unit, "season": s or None,
                    **nat,
                    "national_reported": cur_rep,
                    "national_reported_change": indicator_calc.change(cur_rep, prev_rep)[0],
                    "synthetic": panel.synthetic.get(it.key, False)})
    return {"year": year, "season": season, "items": out, "note": NOTE}


@router.get("/food-security")
def food_security_table(db: Session = Depends(get_db)):
    """Food security score for every district in every year it can be calculated."""
    panel = load_panel(db)
    years = sorted({y for (_, y) in panel.scores})
    rows = []
    for d in sorted(load_district_names()):
        scores = {str(y): panel.scores[(d, y)]["score"] for y in years if (d, y) in panel.scores}
        rows.append({"name": d, "scores": scores})
    return {"years": years, "pillars": PILLAR_LABELS, "districts": rows,
            "synthetic": panel.synthetic.get(FOOD_SECURITY, False), "note": SCORE_NOTE}


@router.get("/food-security.csv")
def food_security_csv(db: Session = Depends(get_db)):
    """The full score table as a CSV: score, change from the year before, and each pillar."""
    panel = load_panel(db)
    buf = io.StringIO()
    w = csv.writer(buf)
    pillars = list(SCORE_PILLARS)
    head = ["data_status", "district", "year", "food_security_score", "change_from_previous_year"]
    for p in pillars:
        head += [f"{p}_raw", f"{p}_scaled_0_100"]
    w.writerow(head)
    status = "SYNTHETIC DEMO - not NISR statistics; do not use for analysis or reporting"
    for (d, y) in sorted(panel.scores, key=lambda k: (k[0], k[1])):
        rec = panel.scores[(d, y)]
        prev = panel.scores.get((d, y - 1))
        change = None if prev is None else round(rec["score"] - prev["score"], 1)
        row = [status, d, y, rec["score"], change]
        for p in pillars:
            row += [rec["pillars"][p]["raw"], rec["pillars"][p]["scaled"]]
        w.writerow(row)
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="food_security_score_DEMO.csv"'})
