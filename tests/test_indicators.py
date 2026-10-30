"""Tests for the district indicators: import, year changes, the food security score and the endpoints.

Expected values below were read by hand from the workbooks in app/data/indicators/ and are noted inline.
"""
import openpyxl
import pytest
from pytest import approx

from app import indicator_calc
from app.db import SessionLocal
from app.districts import load_district_names
from app.importers.indicators import read_district_sheet
from app.models import IndicatorValue
from app.seed import purge_demo


def _count(indicator):
    with SessionLocal() as db:
        return db.query(IndicatorValue).filter_by(indicator=indicator).count()


def test_import_row_counts(client):
    # 30 districts x 26 years = 780 for annual indicators.
    for key in ["within_1km", "grain_reserve", "cows", "goats", "chickens", "pigs", "rabbits", "sheep"]:
        assert _count(key) == 780, key
    # Seasonal: 30 districts x 16 columns (2021-2025 seasons A, B, C and 2026 season A) = 480, plus the
    # national rows from the 'National' sheet (non-blank cells only).
    assert _count("improved_seeds") == 486
    assert _count("inorganic_fertilizer") == 485
    assert _count("organic_fertilizer") == 486
    assert _count("pesticides") == 484


def test_unknown_district_name_stops_the_import(tmp_path):
    path = tmp_path / "bad.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet"
    ws.append(["Title row"])
    ws.append([])
    ws.append(["District", "Province", 2000, 2001])
    ws.append(["Nyarugenge", "Kigali", 1, 2])
    ws.append(["Nyarugen", "Kigali", 1, 2])  # misspelled on purpose
    ws.append(["Mean of districts", None, "=AVERAGE(C4:C5)", "=AVERAGE(D4:D5)"])  # summary row: skipped
    wb.save(path)
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)["Sheet"]
    with pytest.raises(ValueError, match="unknown district name 'Nyarugen'"):
        read_district_sheet(ws, set(load_district_names()))


def test_change_rules_by_hand():
    assert indicator_calc.change(60, 50) == (10, 20.0)
    assert indicator_calc.change(40, 50) == (-10, -20.0)
    assert indicator_calc.change(5, 0) == (5, None)       # no percentage when the previous value is 0
    assert indicator_calc.change(None, 5) == (None, None)
    assert indicator_calc.change(5, None) == (None, None)


def test_scale_handles_flat_range():
    assert indicator_calc.scale(5, 0, 10) == 50
    assert indicator_calc.scale(3, 3, 3) == 50


def test_food_security_toy_example_by_hand():
    # Districts X, Y, M in 2000. Pillar p1 = indicator a. Pillar p2 = average of b and c.
    annual = {
        "a": {("X", 2000): 10, ("Y", 2000): 30, ("M", 2000): 20, ("Q", 2000): 15},
        "b": {("X", 2000): 0, ("Y", 2000): 100, ("M", 2000): 50},
        "c": {("X", 2000): 20, ("Y", 2000): 60, ("M", 2000): 50},
    }
    out = indicator_calc.food_security(annual, {"p1": ["a"], "p2": ["b", "c"]})
    # p1 range 10..30: X=0, Y=100, M=50. p2 raw: X=10, Y=80, M=50; range 10..80: X=0, Y=100, M=57.1.
    assert out[("X", 2000)]["score"] == 0
    assert out[("Y", 2000)]["score"] == 100
    assert out[("M", 2000)]["score"] == approx(53.55, abs=0.06)  # (50 + 57.1) / 2
    assert ("Q", 2000) not in out  # Q has no value for pillar p2, so it cannot be scored


def test_year_change_and_map_match_workbook(client):
    cows = client.get("/api/indicators/map", params={"indicator": "cows", "year": 2025}).json()
    nyar = next(r for r in cows["districts"] if r["name"] == "Nyarugenge")
    # Cattle, Nyarugenge (sheet Cows): 2024 = 25.0, 2025 = 30.6
    assert (nyar["value"], nyar["prev_value"], nyar["change_abs"], nyar["change_pct"]) == (30.6, 25.0, 5.6, 22.4)

    within = client.get("/api/indicators/map", params={"indicator": "within_1km", "year": 2025}).json()
    nyar = next(r for r in within["districts"] if r["name"] == "Nyarugenge")
    # Within 1 km, Nyarugenge: 2024 = 70.6, 2025 = 69.1
    assert (nyar["change_abs"], nyar["change_pct"]) == (-1.5, -2.1)


def test_seasonal_change_is_same_season_previous_year(client):
    seeds = client.get("/api/indicators/map", params={"indicator": "improved_seeds", "year": 2025, "season": "A"}).json()
    nyar = next(r for r in seeds["districts"] if r["name"] == "Nyarugenge")
    # Improved seeds, Nyarugenge: season A 2024 = 41.1, season A 2025 = 46.0
    assert (nyar["value"], nyar["prev_value"], nyar["change_abs"], nyar["change_pct"]) == (46.0, 41.1, 4.9, 11.9)
    assert seeds["seasons"] == ["A", "B", "C"]


def test_national_reported_figures_keep_their_values(client):
    r = client.get("/api/indicators/map", params={"indicator": "improved_seeds", "year": 2023, "season": "A"}).json()
    assert r["national_reported"] == 37.1  # 'National' sheet, 2023 season A
    summary = client.get("/api/indicators/summary", params={"year": 2023, "season": "A"}).json()
    seeds = next(i for i in summary["items"] if i["key"] == "improved_seeds")
    assert seeds["national_reported"] == 37.1


def test_district_panel_lists_every_item_with_changes(client):
    d = client.get("/api/indicators/district", params={"district": "Gisagara", "year": 2025, "season": "A"}).json()
    by_key = {i["key"]: i for i in d["items"]}
    assert len(d["items"]) == 13  # 12 workbook indicators plus the food security score
    # Within 1 km, Gisagara: 2024 = 47.9, 2025 = 51.9
    assert by_key["within_1km"]["value"] == 51.9
    assert by_key["within_1km"]["change_abs"] == 4.0
    assert by_key["food_security"]["change_abs"] is not None


def test_map_values_agree_with_district_panel(client):
    m = client.get("/api/indicators/map", params={"indicator": "cows", "year": 2025}).json()
    d = client.get("/api/indicators/district", params={"district": "Musanze", "year": 2025}).json()
    from_map = next(r for r in m["districts"] if r["name"] == "Musanze")
    from_panel = next(i for i in d["items"] if i["key"] == "cows")
    assert from_map["value"] == from_panel["value"]
    assert from_map["change_abs"] == from_panel["change_abs"]
    for row in m["districts"]:
        if row["value"] is not None and row["prev_value"] is not None:
            assert row["change_abs"] == pytest.approx(row["value"] - row["prev_value"], abs=0.01)


def test_food_security_scores_are_0_to_100_for_every_district_year(client):
    table = client.get("/api/indicators/food-security").json()
    assert table["years"] == list(range(2000, 2026))
    assert len(table["districts"]) == 30
    for row in table["districts"]:
        assert len(row["scores"]) == 26
        assert all(0 <= s <= 100 for s in row["scores"].values())


def test_food_security_csv_has_every_row_and_a_demo_label(client):
    text = client.get("/api/indicators/food-security.csv").text
    lines = text.strip().splitlines()
    assert len(lines) == 1 + 30 * 26
    assert lines[0].startswith("data_status,district,year,food_security_score")
    assert all("SYNTHETIC DEMO" in line for line in lines[1:3])


def test_series_summary_and_catalog_shapes(client):
    s = client.get("/api/indicators/series", params={"indicator": "food_security", "district": "Nyarugenge"}).json()
    assert len(s["points"]) == 26
    assert s["points"][0]["change_abs"] is None  # no earlier year to compare with
    summary = client.get("/api/indicators/summary", params={"year": 2025}).json()
    assert len(summary["items"]) == 13
    catalog = client.get("/api/indicators/catalog").json()
    assert len(catalog["items"]) == 13
    assert all(item["synthetic"] for item in catalog["items"])  # every workbook is synthetic demo data


def test_bad_requests_are_refused(client):
    assert client.get("/api/indicators/map", params={"indicator": "nope"}).status_code == 404
    assert client.get("/api/indicators/series", params={"indicator": "cows", "district": "Atlantis"}).status_code == 404
    assert client.get("/api/indicators/map", params={"indicator": "cows", "year": 1990}).status_code == 422
    assert client.get("/api/indicators/map", params={"indicator": "cows", "season": "Z"}).status_code == 422


def test_purge_removes_synthetic_indicators_and_keeps_national_figures(client):
    with SessionLocal() as db:
        purge_demo(db)
    with SessionLocal() as db:
        assert db.query(IndicatorValue).count() == 21  # only the real national figures remain
