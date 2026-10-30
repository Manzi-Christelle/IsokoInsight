"""Climate forecasts (SYNTHETIC data): the methods, the endpoint, the backtest and the read-only rule."""
import numpy as np
import pytest

from app.db import SessionLocal
from app.ml import forecast_climate as fc
from app.models import ClimateObservation


def test_climatology_and_seasonal_naive_by_hand():
    y = np.arange(36, dtype=float)  # value equals its month index, so January values are 0, 12 and 24
    assert fc.forecast_one("climatology", y, "temp", 1)[0] == pytest.approx(12.0)  # mean of the earlier Januaries
    assert fc.forecast_one("seasonal_naive", y, "temp", 1)[0] == 24.0              # same month last year


def test_rainfall_forecast_is_never_negative():
    rng = np.random.default_rng(1)
    y = np.abs(rng.normal(80, 40, 60))
    f = fc.forecast_one("holt_winters", y, "rain", 6)
    assert len(f) == 6 and (f >= 0).all()


def test_forecast_endpoint_shape_and_label(client):
    r = client.get("/api/forecast/climate", params={"district": "Musanze", "variable": "rain", "horizon": 3}).json()
    assert r["label"].startswith("SYNTHETIC DEMONSTRATION") and r["contains_synthetic"] is True
    assert len(r["forecast"]) == 3 and len(r["history"]) == 24
    months = [(p["year"], p["month"]) for p in r["forecast"]]
    assert months == sorted(months)
    for p in r["forecast"]:
        assert p["point"] >= 0
        if p["lower80"] is not None:
            assert 0 <= p["lower80"] <= p["point"] <= p["upper80"]


def test_forecast_endpoint_rejects_bad_input(client):
    base = {"district": "Musanze", "variable": "rain", "horizon": 3}
    assert client.get("/api/forecast/climate", params={**base, "horizon": 0}).status_code == 422
    assert client.get("/api/forecast/climate", params={**base, "horizon": 301}).status_code == 422
    assert client.get("/api/forecast/climate", params={**base, "horizon": 300}).status_code == 200
    assert client.get("/api/forecast/climate", params={**base, "variable": "snow"}).status_code == 422
    assert client.get("/api/forecast/climate", params={**base, "district": "Atlantis"}).status_code == 404


def test_forecast_does_not_change_the_climate_data(client):
    def count():
        with SessionLocal() as db:
            return db.query(ClimateObservation).count(), db.query(ClimateObservation).filter_by(district="Musanze").all()[0].rain_mm
    before = count()
    client.get("/api/forecast/climate", params={"district": "Musanze", "variable": "rain", "horizon": 6})
    assert count() == before


def test_backtest_summary_structure_on_a_small_subset():
    with SessionLocal() as db:
        series = fc.load_series(db)
    subset = {v: dict(list(ds.items())[:2]) for v, ds in series.items()}
    result = fc.run_backtest(subset, step=12)
    assert result["label"] == fc.LABEL
    block = result["variables"]["rain"]
    assert block["origins"] > 0
    for method in fc.METHODS:
        assert set(block["methods"][method]) == {str(h) for h in range(1, fc.MAX_HORIZON + 1)}
    assert all(0 <= c <= 1 for c in block["holt_winters_80pct_coverage"].values())


def test_saved_backtest_exists_and_is_labelled_synthetic():
    data = fc.load_backtest()
    assert data is not None, "run: python -m app.ml.forecast_climate"
    assert "SYNTHETIC" in data["label"]
