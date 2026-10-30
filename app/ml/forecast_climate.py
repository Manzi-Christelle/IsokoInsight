"""Rainfall and temperature forecasts for each district, with a backtest.

SYNTHETIC DEMONSTRATION DATA. The forecasts are made from the synthetic monthly values in the climate
table. They check that the forecasting method works. They say nothing about real rainfall or temperature
in Rwanda, and they must not be used for planning or reporting.

Methods (the two simple ones are baselines that the smoothing model must beat):
  climatology     the average of the same calendar month in all earlier years
  seasonal_naive  the value of the same calendar month last year
  holt_winters    additive yearly seasonality with a damped trend (statsmodels). Rainfall is modelled on
                  log(1 + mm), so the forecast stays positive and the skew is reduced.

Backtest: for each district, each method is fitted only to the data before a forecast origin and asked
for the next 6 months. The forecast is compared with the synthetic value that actually followed. Origins
are every 3 months, starting after the first three years. The results are saved to
app/ml/artifacts/climate_backtest.json and shown on the Weather and climate tab.

Intervals: an 80 per cent range is the point forecast plus or minus 1.28 times the backtest RMSE for that
horizon. The coverage of these ranges is measured in the backtest and reported with it.

Run the backtest:  python -m app.ml.forecast_climate
"""
import json
import warnings
from datetime import date
from pathlib import Path

import numpy as np

ARTIFACT = Path(__file__).parent / "artifacts" / "climate_backtest.json"
METHODS = ("climatology", "seasonal_naive", "holt_winters")
MAX_HORIZON = 6
MIN_MONTHS = 36          # three full years before the first forecast origin
ORIGIN_STEP = 3          # months between forecast origins
Z80 = 1.2816             # z-value for a central 80 per cent range
UNITS = {"rain": "mm", "temp": "°C"}
LABEL = ("SYNTHETIC DEMONSTRATION. This forecast checks the method only. It is not a forecast of real "
         "rainfall or temperature in Rwanda and must not be used for planning or reporting.")


def forecast_one(method: str, y: np.ndarray, variable: str, horizon: int) -> np.ndarray:
    """Point forecasts for the next `horizon` months. `y` is the monthly series, starting in January."""
    n = len(y)
    if method == "seasonal_naive":
        return np.array([y[n + h - 13] for h in range(1, horizon + 1)])
    if method == "climatology":
        return np.array([y[(n + h - 1) % 12::12].mean() for h in range(1, horizon + 1)])
    if method == "holt_winters":
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        z = np.log1p(y) if variable == "rain" else y
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fit = ExponentialSmoothing(z, trend="add", damped_trend=True, seasonal="add",
                                           seasonal_periods=12, initialization_method="estimated").fit()
                f = np.asarray(fit.forecast(horizon), dtype=float)
        except Exception:  # the smoothing model failed to fit: fall back to the climatology baseline
            return forecast_one("climatology", y, variable, horizon)
        if variable == "rain":
            return np.maximum(np.expm1(f), 0.0)
        return f
    raise ValueError(f"Unknown method: {method}")


def load_series(db) -> dict[str, dict[str, np.ndarray]]:
    """{variable: {district: monthly values, oldest first}} from the climate table."""
    from ..models import ClimateObservation
    rows = (db.query(ClimateObservation)
            .order_by(ClimateObservation.district, ClimateObservation.year, ClimateObservation.month).all())
    by = {"rain": {}, "temp": {}}
    for r in rows:
        by["rain"].setdefault(r.district, []).append(r.rain_mm)
        by["temp"].setdefault(r.district, []).append(r.temp_c)
    return {v: {d: np.array(vals, dtype=float) for d, vals in ds.items()} for v, ds in by.items()}


def run_backtest(series: dict[str, dict[str, np.ndarray]], step: int = ORIGIN_STEP) -> dict:
    """Backtest every method on every district and summarise the errors by variable, method and horizon."""
    errors = {v: {m: {h: [] for h in range(1, MAX_HORIZON + 1)} for m in METHODS} for v in series}
    origins = {v: 0 for v in series}
    for variable, by_district in series.items():
        for y in by_district.values():
            for origin in range(MIN_MONTHS, len(y) - MAX_HORIZON + 1, step):
                actual = y[origin:origin + MAX_HORIZON]
                origins[variable] += 1
                for method in METHODS:
                    pred = forecast_one(method, y[:origin], variable, MAX_HORIZON)
                    for h in range(1, MAX_HORIZON + 1):
                        errors[variable][method][h].append(float(actual[h - 1] - pred[h - 1]))

    variables = {}
    for v in series:
        block = {"unit": UNITS[v], "origins": origins[v], "methods": {}}
        for m in METHODS:
            per_h = {}
            for h in range(1, MAX_HORIZON + 1):
                e = np.array(errors[v][m][h])
                per_h[str(h)] = {"mae": round(float(np.mean(np.abs(e))), 2),
                                 "rmse": round(float(np.sqrt(np.mean(e ** 2))), 2),
                                 "bias": round(float(np.mean(e)), 2), "n": int(e.size)}
            block["methods"][m] = per_h
        coverage = {}
        for h in range(1, MAX_HORIZON + 1):
            e = np.array(errors[v]["holt_winters"][h])
            half = Z80 * block["methods"]["holt_winters"][str(h)]["rmse"]
            coverage[str(h)] = round(float(np.mean(np.abs(e) <= half)), 3)
        block["holt_winters_80pct_coverage"] = coverage
        variables[v] = block
    return {"label": LABEL, "generated_on": date.today().isoformat(), "districts": len(next(iter(series.values()))),
            "origin_step_months": step, "methods": list(METHODS), "variables": variables}


def load_backtest() -> dict | None:
    try:
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def district_forecast(rows, variable: str, horizon: int, backtest: dict | None) -> dict:
    """Forecast for one district. `rows` are its ClimateObservation rows, oldest first.

    Ranges are only given for the months the backtest tested (1 to MAX_HORIZON).
    Further ahead the value only continues the smoothed seasonal pattern and has no tested range.
    """
    y = np.array([r.rain_mm if variable == "rain" else r.temp_c for r in rows], dtype=float)
    points = forecast_one("holt_winters", y, variable, horizon)

    months, yy, mm = [], rows[-1].year, rows[-1].month
    for _ in range(horizon):
        mm += 1
        if mm == 13:
            yy, mm = yy + 1, 1
        months.append((yy, mm))

    hw = backtest["variables"][variable]["methods"]["holt_winters"] if backtest else None
    forecast = []
    for i, (fy, fm) in enumerate(months):
        p = float(points[i])
        h = i + 1
        if hw and str(h) in hw:
            half = Z80 * hw[str(h)]["rmse"]
            lo, hi = p - half, p + half
            if variable == "rain":
                lo = max(lo, 0.0)
            lo, hi = round(lo, 1), round(hi, 1)
        else:
            lo = hi = None
        forecast.append({"year": fy, "month": fm, "point": round(p, 1), "lower80": lo, "upper80": hi})

    history = [{"year": r.year, "month": r.month, "value": round(float(v), 1)}
               for r, v in zip(rows[-24:], y[-24:])]

    table = None
    if backtest:
        block = backtest["variables"][variable]["methods"]
        table = []
        for h in range(1, min(horizon, MAX_HORIZON) + 1):
            hw_mae = block["holt_winters"][str(h)]["mae"]
            clim_mae = block["climatology"][str(h)]["mae"]
            table.append({"horizon": h, "holt_winters_mae": hw_mae, "seasonal_naive_mae": block["seasonal_naive"][str(h)]["mae"],
                          "climatology_mae": clim_mae, "beats_climatology": hw_mae < clim_mae})
    return {"history": history, "forecast": forecast, "backtest_table": table,
            "backtest_generated_on": backtest["generated_on"] if backtest else None,
            "backtest_origins": backtest["variables"][variable]["origins"] if backtest else None}


if __name__ == "__main__":
    from ..db import SessionLocal
    with SessionLocal() as session:
        series = load_series(session)
    result = run_backtest(series)
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Backtest written to {ARTIFACT}")
    for v, block in result["variables"].items():
        print(f"\n{v} ({block['unit']}), {block['origins']} forecast origins")
        print("horizon  holt-winters MAE  seasonal naive MAE  climatology MAE  80% coverage")
        for h in range(1, MAX_HORIZON + 1):
            m = block["methods"]
            print(f"{h:>7}  {m['holt_winters'][str(h)]['mae']:>16}  {m['seasonal_naive'][str(h)]['mae']:>18}"
                  f"  {m['climatology'][str(h)]['mae']:>15}  {block['holt_winters_80pct_coverage'][str(h)]:>11}")
