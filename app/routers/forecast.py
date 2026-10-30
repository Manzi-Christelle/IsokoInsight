from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..districts import load_district_names
from ..ml.forecast_climate import LABEL, MIN_MONTHS, UNITS, district_forecast, load_backtest
from ..models import ClimateObservation

router = APIRouter(prefix="/api/forecast", tags=["forecasts (machine estimates)"])

MAX_FORECAST_MONTHS = 300  # January 2026 to December 2050
NON_SYNTHETIC_LABEL = "Machine estimate from the data loaded here. Read the method note before using it."

# Forecasts are worked out once per district, variable and horizon, then reused.
# The cache is cleared when the server restarts.
_forecast_cache: dict[tuple[str, str, int], dict] = {}
_backtest_cache: dict | None = None
_backtest_loaded = False


def _backtest() -> dict | None:
    global _backtest_cache, _backtest_loaded
    if not _backtest_loaded:
        _backtest_cache = load_backtest()
        _backtest_loaded = True
    return _backtest_cache


@router.get("/climate")
def climate_forecast(district: str,
                     variable: str = Query("rain", pattern="^(rain|temp)$"),
                     horizon: int = Query(3, ge=1, le=MAX_FORECAST_MONTHS),
                     db: Session = Depends(get_db)):
    """Rainfall or temperature forecast for one district, up to December 2050 (300 months).

    SYNTHETIC DEMONSTRATION DATA. The forecast checks the method only. It is not a forecast of real weather.
    Ranges are only given for the first 6 months, the period the backtest tested.
    """
    key = (district, variable, horizon)
    if key in _forecast_cache:
        return _forecast_cache[key]

    if district not in load_district_names():
        raise HTTPException(404, "Unknown district")
    rows = (db.query(ClimateObservation).filter_by(district=district)
            .order_by(ClimateObservation.year, ClimateObservation.month).all())
    if len(rows) < MIN_MONTHS:
        raise HTTPException(404, "Not enough climate data for this district")

    synthetic = any(r.source.is_synthetic for r in rows)
    result = district_forecast(rows, variable, horizon, _backtest())
    payload = {
        "label": LABEL if synthetic else NON_SYNTHETIC_LABEL,
        "contains_synthetic": synthetic,
        "district": district,
        "variable": variable,
        "unit": UNITS[variable],
        "method": "Holt-Winters smoothing with yearly seasonality and a damped trend",
        "method_note": ("Rainfall is smoothed on a log scale so forecasts stay positive. Ranges are 80 per cent "
                        "ranges from the backtest error for each horizon."),
        "source": rows[-1].source.name,
        **result,
    }
    _forecast_cache[key] = payload
    return payload