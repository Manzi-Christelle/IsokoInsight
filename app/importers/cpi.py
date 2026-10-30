"""Importer for monthly CPI tables (NISR style).

Handles the problems found in the raw NISR file: non-UTF-8 encoding, title rows above the
header, stray values in the footer, and weights stored as text such as " 10,000 ".
Accepts either layout: months in rows (one column per series) or months in columns.
Always check the parsed result against the original file before trusting it.
"""
import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy.orm import Session

from ..models import DataSource, OfficialSeries, OfficialValue

_DATE_FORMATS = ("%Y-%m", "%b-%Y", "%b %Y", "%B %Y", "%B-%Y", "%Y-%m-%d", "%m/%Y",
                 "%Y/%m", "%b-%y", "%b %y", "%d/%m/%Y")
_FOOD_SUBGROUP_WORDS = ("bread", "cereal", "meat", "fish", "milk", "cheese", "egg", "oils",
                        "fruit", "vegetable", "sugar", "jam", "honey", "confectionery",
                        "non-alcoholic", "non alcoholic")


@dataclass
class ParsedCPI:
    series: dict[str, dict[date, float]] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def decode_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def parse_period(text: str) -> date | None:
    t = text.strip()
    m = re.fullmatch(r"(\d{4})\s*M(\d{1,2})", t, flags=re.I)  # 2009M02
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)
    if not re.search(r"[A-Za-z/\-]", t):  # plain numbers such as 102.1 are not dates
        return None
    for fmt in _DATE_FORMATS:
        try:
            d = datetime.strptime(t, fmt)
            return date(d.year, d.month, 1)
        except ValueError:
            continue
    return None


def parse_number(text: str) -> float | None:
    t = text.strip().replace(" ", "")
    if not t or t in {"-", "..", "n/a", "NA"}:
        return None
    t = re.sub(r"(?<=\d),(?=\d{3}(\D|$))", "", t)  # 10,000 -> 10000
    try:
        return float(t)
    except ValueError:
        return None


def _read_rows(raw: bytes) -> list[list[str]]:
    text = decode_bytes(raw)
    sample = text[:4000]
    delim = max([",", ";", "\t"], key=sample.count)
    return [[c.strip() for c in row] for row in csv.reader(io.StringIO(text), delimiter=delim)]


def parse_cpi(raw: bytes) -> ParsedCPI:
    rows = _read_rows(raw)
    out = ParsedCPI()

    # Layout A: months in rows, series in columns.
    date_rows = [i for i, r in enumerate(rows) if r and parse_period(r[0])]
    # Layout B: months in columns (header row where most cells after the first are dates).
    header_b = next((i for i, r in enumerate(rows)
                     if len(r) > 6 and sum(1 for c in r[1:] if parse_period(c)) >= 0.7 * (len(r) - 1)), None)

    if len(date_rows) >= 6 and header_b is None:
        first = date_rows[0]
        header_idx = next(i for i in range(first - 1, -1, -1)
                          if sum(1 for c in rows[i] if c) >= 3 and not rows[i][0].lower().startswith("weight"))
        header = rows[header_idx]
        names = {j: n for j, n in enumerate(header) if j > 0 and n}
        for j, name in names.items():
            out.series[name] = {}
        for r in rows[header_idx + 1:]:
            if not r:
                continue
            if r[0].lower().startswith("weight"):
                for j, name in names.items():
                    w = parse_number(r[j]) if j < len(r) else None
                    if w is not None:
                        out.weights[name] = w
                continue
            p = parse_period(r[0])
            if not p:
                continue  # footer / stray rows
            for j, name in names.items():
                v = parse_number(r[j]) if j < len(r) else None
                if v is not None:
                    out.series[name][p] = v
    elif header_b is not None:
        header = rows[header_b]
        periods = {j: parse_period(c) for j, c in enumerate(header) if j > 0 and parse_period(c)}
        weight_col = next((j for j, c in enumerate(header) if "weight" in c.lower()), None)
        for r in rows[header_b + 1:]:
            if not r or not r[0]:
                continue
            vals = {p: parse_number(r[j]) for j, p in periods.items() if j < len(r)}
            vals = {p: v for p, v in vals.items() if v is not None}
            if len(vals) >= 3:
                out.series[r[0]] = vals
                if weight_col is not None and weight_col < len(r):
                    w = parse_number(r[weight_col])
                    if w is not None:
                        out.weights[r[0]] = w
    else:
        raise ValueError("Could not find month labels in the file. Expected rows or columns "
                         "such as 'Feb-2009' or '2009-02'.")

    out.series = {k: v for k, v in out.series.items() if len(v) >= 3}
    if not out.series:
        raise ValueError("No numeric series found.")
    out.warnings.append("Group labels (headline/division/food sub-group) are assigned by "
                        "name matching; review them against the NISR COICOP list.")
    return out


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def classify(name: str) -> str:
    n = name.lower()
    if "general" in n or n in {"all items", "headline", "overall index"}:
        return "headline"
    if "food" in n:
        return "division"
    if any(w in n for w in _FOOD_SUBGROUP_WORDS) and "alcoholic beverages and" not in n:
        return "food_subgroup"
    return "division"


def load_cpi(db: Session, parsed: ParsedCPI, source: DataSource) -> dict:
    """Upsert parsed series into the database (safe to run twice)."""
    n_series = n_values = 0
    for name, points in parsed.series.items():
        code = slugify(name)
        s = db.query(OfficialSeries).filter_by(code=code).one_or_none()
        if not s:
            s = OfficialSeries(code=code, name=name, group=classify(name), source_id=source.id)
            db.add(s)
            db.flush()
            n_series += 1
        if name in parsed.weights:
            s.weight = parsed.weights[name]
        existing = {v.period: v for v in db.query(OfficialValue).filter_by(series_id=s.id)}
        for period, value in points.items():
            if period in existing:
                existing[period].index_value = value
            else:
                db.add(OfficialValue(series_id=s.id, period=period, index_value=value))
                n_values += 1
    db.commit()
    return {"series_created": n_series, "values_added": n_values, "warnings": parsed.warnings}
