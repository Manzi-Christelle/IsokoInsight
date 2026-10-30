"""Loads the indicator values from the database and adds the food security score."""
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from . import indicator_calc
from .indicators import FOOD_SECURITY, NATIONAL, SCORE_PILLARS
from .models import DataSource, IndicatorValue


@dataclass
class Panel:
    values: dict = field(default_factory=dict)      # key -> {(district, year, season): value}
    synthetic: dict = field(default_factory=dict)   # key -> True when any value comes from synthetic demo data
    scores: dict = field(default_factory=dict)      # (district, year) -> {"score", "pillars"}

    def series(self, key: str) -> dict:
        return self.values.get(key, {})


def load_panel(db: Session) -> Panel:
    rows = (db.query(IndicatorValue.indicator, IndicatorValue.district, IndicatorValue.year,
                     IndicatorValue.season, IndicatorValue.value, DataSource.is_synthetic)
            .join(DataSource, IndicatorValue.source_id == DataSource.id).all())
    values = defaultdict(dict)
    synthetic = defaultdict(bool)
    for key, district, year, season, value, is_syn in rows:
        values[key][(district, year, season)] = value
        synthetic[key] = synthetic[key] or bool(is_syn)

    pillar_keys = {k for keys in SCORE_PILLARS.values() for k in keys}
    annual = {k: {(d, y): v for (d, y, s), v in values[k].items() if s == "" and d != NATIONAL}
              for k in pillar_keys}
    scores = indicator_calc.food_security(annual, SCORE_PILLARS)
    values[FOOD_SECURITY] = {(d, y, ""): rec["score"] for (d, y), rec in scores.items()}
    synthetic[FOOD_SECURITY] = any(synthetic[k] for k in pillar_keys)
    return Panel(values=dict(values), synthetic=dict(synthetic), scores=scores)
