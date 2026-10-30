"""District weather and its likely effect on farming. SYNTHETIC DEMONSTRATION DATA.

Rainfall and temperature are generated for the prototype. The generator follows Rwanda's broad pattern
(two rainy seasons: long rains March to May, short rains September to November; cooler highlands; a
hotter, drier east) but the values are NOT observations from the Rwanda Meteorology Agency.

Method (documented in docs/METHODOLOGY.md):
  normal rainfall          = the district's average annual rainfall over the baseline years 2016-2025
  rainfall vs normal (%)   = (year total - normal) / normal x 100
  temperature vs normal    = year mean temperature - the district's average over the baseline years
  impact class             = from rainfall vs normal, using IMPACT_BANDS
"""
import math
import random
from statistics import mean

BASELINE_YEARS = list(range(2016, 2026))
CLIMATE_YEARS = BASELINE_YEARS

DISTRICT_PROVINCE = {
    "Gasabo": "Kigali City", "Kicukiro": "Kigali City", "Nyarugenge": "Kigali City",
    "Gisagara": "Southern", "Huye": "Southern", "Kamonyi": "Southern", "Muhanga": "Southern",
    "Nyamagabe": "Southern", "Nyanza": "Southern", "Nyaruguru": "Southern", "Ruhango": "Southern",
    "Karongi": "Western", "Ngororero": "Western", "Nyabihu": "Western", "Nyamasheke": "Western",
    "Rubavu": "Western", "Rusizi": "Western", "Rutsiro": "Western",
    "Burera": "Northern", "Gakenke": "Northern", "Gicumbi": "Northern", "Musanze": "Northern",
    "Rulindo": "Northern",
    "Bugesera": "Eastern", "Gatsibo": "Eastern", "Kayonza": "Eastern", "Kirehe": "Eastern",
    "Ngoma": "Eastern", "Nyagatare": "Eastern", "Rwamagana": "Eastern",
}

# Province baseline: annual rainfall (mm) and mean temperature (C) before district and year variation.
PROVINCE_CLIMATE = {
    "Kigali City": (1080.0, 20.5),
    "Southern": (1150.0, 20.0),
    "Western": (1250.0, 19.0),
    "Northern": (1300.0, 17.5),
    "Eastern": (920.0, 22.0),
}

# Share of the year's rain in each month (sums to 1.0): long rains Mar-May, short rains Sep-Nov.
MONTH_SHARE = [0.07, 0.08, 0.12, 0.13, 0.09, 0.04, 0.03, 0.05, 0.08, 0.11, 0.12, 0.08]

# Built-in events so the comparison has something to show: (year, province) -> rainfall multiplier.
RAIN_EVENTS = {(2022, "Eastern"): 0.74, (2022, "Southern"): 0.88,
               (2020, "Northern"): 1.18, (2020, "Western"): 1.15}
# Year -> temperature shift applied to the whole country (C).
TEMP_EVENTS = {2023: 0.4, 2024: 1.0}

# Rainfall vs normal (%) -> impact class. Lower bound is inclusive, upper bound exclusive.
IMPACT_CLASSES = [
    # key, label, colour, text for farmers
    ("severe_dry", "Severe dry (drought stress)", "#8c510a",
     "Drought stress. Rain-fed maize, beans and Irish potatoes may yield much less. Plant "
     "drought-tolerant seed where possible and make sure livestock have water."),
    ("dry", "Dry (below normal rain)", "#d8b365",
     "Below-normal rain. Check soil moisture before planting and delay if the rains are late. "
     "Pasture may thin."),
    ("normal", "Normal rain", "#e9e4d6",
     "Near-normal rain. The usual planting calendar should work for rain-fed crops."),
    ("wet", "Wet (above normal rain)", "#5ab4ac",
     "Above-normal rain. Good for crops and pasture, but watch for fungal disease and waterlogging."),
    ("very_wet", "Very wet (flood risk)", "#01665e",
     "Very wet season. Low fields may flood and slopes may slip; waterlogged soil can rot crops."),
]
IMPACT_BOUNDS = [-20.0, -10.0, 10.0, 20.0]  # between the five classes, in order
HEAT_TEXT = " Temperatures are also above normal, which adds heat stress for dairy cattle and can cut yields."
HEAT_THRESHOLD_C = 0.8

TEMP_CLASSES = [
    ("cooler", "Cooler than normal", "#4575b4"),
    ("near", "Near normal", "#e9e4d6"),
    ("warmer", "Warmer than normal", "#f4a582"),
    ("much_warmer", "Much warmer than normal", "#b2182b"),
]
TEMP_BOUNDS = [-0.5, 0.5, 1.0]

NOTE = ("SYNTHETIC DEMONSTRATION DATA. Rainfall and temperature are randomly generated for the prototype. "
        "They are NOT observations from the Rwanda Meteorology Agency and must not be used for planning.")
IMPACT_NOTE = ("Impact text is a general guide to what a rainfall pattern usually means for farming. "
               "It is not a forecast and not a crop-specific recommendation.")


def simulate(rng: random.Random) -> list[tuple[str, int, int, float, float]]:
    """Return (district, year, month, rain_mm, temp_c) rows for every district and baseline year."""
    rows = []
    for district in sorted(DISTRICT_PROVINCE):
        province = DISTRICT_PROVINCE[district]
        base_rain, base_temp = PROVINCE_CLIMATE[province]
        d_rain = base_rain * rng.uniform(0.95, 1.05)       # each district differs a little
        d_temp = rng.uniform(-0.4, 0.4)
        for year in CLIMATE_YEARS:
            year_rain = d_rain * RAIN_EVENTS.get((year, province), 1.0) * rng.gauss(1.0, 0.07)
            year_temp = TEMP_EVENTS.get(year, 0.0) + rng.gauss(0.0, 0.15)
            for m in range(12):
                rain = year_rain * MONTH_SHARE[m] * rng.uniform(0.85, 1.15)
                temp = (base_temp + d_temp + year_temp + 0.4 * math.cos(2 * math.pi * m / 12)
                        + rng.gauss(0.0, 0.3))
                rows.append((district, year, m + 1, round(rain, 1), round(temp, 1)))
    return rows


def impact_class(rain_vs_normal_pct: float) -> str:
    """Map rainfall vs normal (%) to an impact class key."""
    lo, lo_mid, hi_mid, hi = IMPACT_BOUNDS
    if rain_vs_normal_pct <= lo:
        return "severe_dry"
    if rain_vs_normal_pct < lo_mid:
        return "dry"
    if rain_vs_normal_pct < hi_mid:
        return "normal"
    if rain_vs_normal_pct < hi:
        return "wet"
    return "very_wet"


def temp_class(temp_vs_normal_c: float) -> str:
    cooler, warmer, much = TEMP_BOUNDS
    if temp_vs_normal_c <= cooler:
        return "cooler"
    if temp_vs_normal_c < warmer:
        return "near"
    if temp_vs_normal_c < much:
        return "warmer"
    return "much_warmer"


def impact_text(rain_class: str, temp_vs_normal_c: float) -> str:
    text = next(t for key, _, _, t in IMPACT_CLASSES if key == rain_class)
    if temp_vs_normal_c >= HEAT_THRESHOLD_C:
        text += HEAT_TEXT
    return text


def district_summary(months: dict[int, tuple[float, float]], normal_rain: float, normal_temp: float) -> dict:
    """months: {month: (rain_mm, temp_c)} for one district and one year (12 months expected).

    Returns annual rainfall, its difference from normal, mean temperature and the impact classes.
    """
    rain = sum(months[m][0] for m in range(1, 13))
    temp = mean(months[m][1] for m in range(1, 13))
    rain_pct = (rain - normal_rain) / normal_rain * 100.0
    temp_diff = temp - normal_temp
    rain_key = impact_class(rain_pct)
    return {
        "rain_mm": round(rain, 1), "rain_normal_mm": round(normal_rain, 1),
        "rain_vs_normal_pct": round(rain_pct, 1),
        "temp_c": round(temp, 1), "temp_normal_c": round(normal_temp, 1),
        "temp_vs_normal_c": round(temp_diff, 2),
        "impact_class": rain_key,
        "impact_label": next(label for key, label, _, _ in IMPACT_CLASSES if key == rain_key),
        "impact_text": impact_text(rain_key, temp_diff),
        "temp_class": temp_class(temp_diff),
    }


def build_table(rows) -> dict:
    """rows: objects with district, year, month, rain_mm, temp_c.
    Returns {district: {year: {month: (rain, temp)}}}."""
    table: dict[str, dict[int, dict[int, tuple[float, float]]]] = {}
    for r in rows:
        table.setdefault(r.district, {}).setdefault(r.year, {})[r.month] = (r.rain_mm, r.temp_c)
    return table


def normals(table: dict, district: str) -> tuple[float, float] | None:
    """Average annual rainfall and average mean temperature over the baseline years."""
    years = table.get(district, {})
    full = [y for y in BASELINE_YEARS if y in years and len(years[y]) == 12]
    if not full:
        return None
    annual = [sum(years[y][m][0] for m in range(1, 13)) for y in full]
    temps = [mean(years[y][m][1] for m in range(1, 13)) for y in full]
    return mean(annual), mean(temps)


def district_year(table: dict, district: str, year: int) -> dict | None:
    """Summary for one district and year, or None if the data is missing."""
    norm = normals(table, district)
    months = table.get(district, {}).get(year)
    if norm is None or not months or len(months) != 12:
        return None
    return district_summary(months, norm[0], norm[1])


RAIN_RANGES = ["20% or more below normal", "10% to 20% below normal", "within 10% of normal",
               "10% to 20% above normal", "20% or more above normal"]
TEMP_RANGES = ["0.5 C or more cooler", "0.5 C cooler to 0.5 C warmer", "0.5 C to 1.0 C warmer",
               "1.0 C or more warmer"]


def legend_for(metric: str) -> list[dict]:
    if metric == "temp":
        return [{"key": k, "label": label, "colour": c, "range": r}
                for (k, label, c), r in zip(TEMP_CLASSES, TEMP_RANGES)]
    return [{"key": k, "label": label, "colour": c, "range": r}
            for (k, label, c, _), r in zip(IMPACT_CLASSES, RAIN_RANGES)]
