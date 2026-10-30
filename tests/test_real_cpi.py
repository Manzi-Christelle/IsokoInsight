"""Tests for the real NISR CPI table (All Rwanda, from CPI_time_series_August_2026.xls).

The expected figures are the index values in the NISR file. Year-on-year inflation was worked out by hand:
August 2026 = 241.3668 / 208.32 - 1 = 15.86%, shown as 15.9%. July 2026 = 235.3338 / 206.88 - 1 = 13.75%, 13.8%.
"""
import pytest

from app.importers.cpi import parse_cpi
from app.seed import NISR_CPI_FILE
from app.db import SessionLocal
from app.models import DataSource, OfficialIndicator, OfficialSeries, OfficialValue
from datetime import date


@pytest.fixture()
def parsed():
    return parse_cpi(NISR_CPI_FILE.read_bytes())


def test_real_file_parses_to_all_rwanda_series(parsed):
    assert len(parsed.series) == 18
    general = parsed.series["00 GENERAL INDEX (CPI)"]
    assert min(general) == date(2009, 2, 1) and max(general) == date(2026, 8, 1) and len(general) == 211
    assert general[date(2026, 8, 1)] == pytest.approx(241.3668)
    assert general[date(2025, 8, 1)] == pytest.approx(208.32, abs=0.01)
    assert parsed.weights["00 GENERAL INDEX (CPI)"] == 10000


def test_headline_inflation_is_calculated_from_the_index(client):
    with SessionLocal() as db:
        src = db.query(DataSource).filter_by(name="NISR CPI time series, All Rwanda (August 2026 release)").one()
        assert src.is_synthetic is False
        rows = {r.period: r.value for r in db.query(OfficialIndicator).filter_by(source_id=src.id)}
    assert rows[date(2026, 8, 1)] == 15.9
    assert rows[date(2026, 7, 1)] == 13.8
    assert len(rows) == 199  # every month from February 2010, when a year-earlier value exists


def test_typed_figures_and_demo_cpi_are_gone(client):
    with SessionLocal() as db:
        assert db.query(DataSource).filter_by(name="NISR Consumer Price Index release, August 2026").count() == 0
        assert db.query(DataSource).filter_by(name="DEMO - synthetic CPI series").count() == 0
        names = {s.name for s in db.query(OfficialSeries)}
        assert "00 GENERAL INDEX (CPI)" in names and "General Index" not in names
        assert db.query(OfficialIndicator).filter(OfficialIndicator.name.like("Energy%")).count() == 0
