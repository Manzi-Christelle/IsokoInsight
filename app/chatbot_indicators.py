"""IsokoBot answers about the district indicators (grain reserve, livestock, farm inputs, market access
and the food security score).

The question is matched to one or more indicators, a district and a year. The answer quotes the stored
value for exactly that district and year, and says so when the value is synthetic demo data. When no
district is named, it lists the highest and lowest districts for the year.
"""
import re

from sqlalchemy.orm import Session

from .indicator_data import load_panel
from .indicators import BY_KEY, FOOD_SECURITY, SOURCE_NAMES

FIRST_YEAR, LAST_YEAR = 2000, 2025  # the years the indicator workbooks cover
SEASONS = ("A", "B", "C")

# Ways people refer to each indicator. Each pattern is matched as whole words, so "organic" does not match
# "inorganic". Generic "fertilizer" with no qualifier matches both fertiliser indicators.
ALIASES = {
    "within_1km": [r"within 1 ?km", r"1 ?km", r"market access", r"near (a |the )?market"],
    "grain_reserve": [r"grains?", r"reserves?", r"storage"],
    "cows": [r"cows?", r"cattle"],
    "goats": [r"goats?"],
    "chickens": [r"chickens?", r"poultry"],
    "pigs": [r"pigs?"],
    "rabbits": [r"rabbits?"],
    "sheep": [r"sheep"],
    "improved_seeds": [r"improved seeds?", r"seeds?"],
    "inorganic_fertilizer": [r"inorganic( fertili[sz]ers?)?", r"chemical fertili[sz]ers?"],
    "organic_fertilizer": [r"organic( fertili[sz]ers?)?", r"manure"],
    "pesticides": [r"pesticides?"],
    FOOD_SECURITY: [r"food security", r"security score"],
}
GENERIC_FERTILISER = ("inorganic_fertilizer", "organic_fertilizer")

def match_indicators(text: str) -> list[str]:
    keys = []
    for key, patterns in ALIASES.items():
        if any(re.search(r"\b" + p + r"\b", text) for p in patterns):
            keys.append(key)
    if not any(k in keys for k in GENERIC_FERTILISER) and re.search(r"\bfertili[sz]ers?\b", text):
        keys.extend(GENERIC_FERTILISER)
    # keep one entry per indicator, in catalogue order
    order = {k: i for i, k in enumerate(ALIASES)}
    return sorted(set(keys), key=lambda k: order[k])


def requested_year(text: str) -> int | None:
    m = re.search(r"\b(20\d{2}|19\d{2})\b", text)
    return int(m.group(1)) if m else None


def requested_season(text: str) -> str | None:
    m = re.search(r"\bseason\s*([abc])\b", text)
    return m.group(1).upper() if m else None


def _years_covered(series: dict) -> str:
    years = sorted({y for (_, y, _) in series})
    return f"{years[0]} to {years[-1]}" if years else "no years"


def _fmt(v: float) -> str:
    return f"{v:,.1f}"


def _sources_for(key: str) -> str:
    item = BY_KEY[key]
    if item.group == "score":
        return "Calculated from the DEMO indicator workbooks (synthetic)"
    return SOURCE_NAMES.get(item.group, "District indicator workbooks")


def _change(cur: float | None, prev: float | None) -> str:
    if cur is None or prev in (None, 0):
        return ""
    pct = (cur - prev) / prev * 100
    return f" That is {pct:+.1f}% against the year before ({_fmt(prev)})."


def indicator_answer(db: Session, keys: list[str], district: str | None, year: int | None,
                     season: str | None) -> tuple[str, list[str]]:
    year = year or LAST_YEAR
    if not FIRST_YEAR <= year <= LAST_YEAR:
        return (f"No data found for {year}. These indicators cover {FIRST_YEAR} to {LAST_YEAR}.", [])
    panel = load_panel(db)
    lines, sources, demo = [], [], False
    for key in keys:
        item = BY_KEY[key]
        series = panel.series(key)
        seasons = ([season] if season else ["A"]) if item.seasonal else [""]
        if item.seasonal and not season and district:
            seasons = list(SEASONS)
        sources.append(_sources_for(key))
        demo = demo or panel.synthetic.get(key, False)
        label = item.label + (" (season {})" if item.seasonal else "")
        if district:
            for s in seasons:
                cur = series.get((district, year, s))
                prev = series.get((district, year - 1, s))
                name = label.format(s) if item.seasonal else label
                if cur is None:
                    lines.append(f"{name} in {district}, {year}: no value in the data. "
                                 f"This indicator covers {_years_covered(series)}.")
                else:
                    lines.append(f"{name} in {district}, {year}: {_fmt(cur)} {item.unit}.{_change(cur, prev)}")
        else:
            s = seasons[0]
            ranked = sorted(((v, d) for (d, y, sea), v in series.items() if y == year and sea == s), reverse=True)
            name = label.format(s) if item.seasonal else label
            if not ranked:
                lines.append(f"{name}, {year}: no value in the data.")
                continue
            unit = "" if item.unit.startswith("score") else f" ({item.unit})"
            lines.append(f"{name}, {year}{unit}. Highest: "
                         + ", ".join(f"{d} {_fmt(v)}" for v, d in ranked[:5])
                         + ". Lowest: " + ", ".join(f"{d} {_fmt(v)}" for v, d in ranked[-3:][::-1]) + ".")
    if demo:
        lines.append("DEMO DATA: these values are synthetic examples, not NISR or census statistics.")
    return "\n".join(lines), sorted(set(sources))
