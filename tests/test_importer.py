from datetime import date

import pytest

from app.importers.cpi import classify, parse_cpi, parse_number, parse_period


def test_parse_helpers():
    assert parse_period("Feb-2009") == date(2009, 2, 1)
    assert parse_period("2009-02") == date(2009, 2, 1)
    assert parse_period("2009M02") == date(2009, 2, 1)
    assert parse_period("102.1") is None            # stray footer value is not a date
    assert parse_number(" 10,000 ") == 10000.0       # weights stored as text
    assert parse_number("241.4") == 241.4


def _months_in_rows():
    lines = ["Consumer Price Index - All Rwanda", "Base February 2014 = 100", "",
             "Period,General Index,Food and non-alcoholic beverages,Meat"]
    lines.append('Weight," 10,000 "," 3,904 ", 400')
    for i in range(8):
        lines.append(f"2026-{i + 1:02d}-01,{200 + i},{210 + i},{300 + i}" if False else f"Jan-{2020 + i},{100 + i},{110 + i},{120 + i}")
    lines.append("102.1")  # stray footer value
    return "\n".join(lines)


def test_months_in_rows_layout_with_messy_file():
    raw = _months_in_rows().encode("cp1252")
    parsed = parse_cpi(raw)
    assert set(parsed.series) == {"General Index", "Food and non-alcoholic beverages", "Meat"}
    assert parsed.series["General Index"][date(2020, 1, 1)] == 100.0
    assert len(parsed.series["Meat"]) == 8               # footer row ignored
    assert parsed.weights["Food and non-alcoholic beverages"] == 3904.0


def test_months_in_columns_layout():
    cols = ",".join(f"Jan-{2015 + i}" for i in range(8))
    raw = f"Title row\nCategory,Weight,{cols}\nGeneral Index, 10,000 ,".replace(", 10,000 ,", ',"10,000",')
    raw += ",".join(str(100 + i) for i in range(8)) + "\n"
    raw += "Meat,400," + ",".join(str(90 + i) for i in range(8)) + "\n"
    parsed = parse_cpi(raw.encode("utf-8"))
    assert parsed.series["Meat"][date(2015, 1, 1)] == 90.0
    assert parsed.weights["General Index"] == 10000.0


def test_rejects_file_without_months():
    with pytest.raises(ValueError):
        parse_cpi(b"a,b,c\n1,2,3\n")


def test_classify():
    assert classify("General Index") == "headline"
    assert classify("Food and non-alcoholic beverages") == "division"
    assert classify("Meat") == "food_subgroup"
    assert classify("Alcoholic beverages and tobacco") == "division"
    assert classify("Transport") == "division"
