import re
from collections import defaultdict

from sqlalchemy.orm import Session

from . import climate
from .models import ClimateObservation
from .ml.forecast_climate import MAX_HORIZON, MIN_MONTHS, UNITS, district_forecast, load_backtest

CLIMATE_WORDS = r"(rain|rainfall|rainy|temperature|temperatures|hot|heat|weather|climate|drought|dry|wet|farming impact)"
FORECAST_WORDS = r"(forecast\w*|predict\w*|prediction\w*|projection\w*|outlook|expected|until|next \d+ months?)"
EXPLAIN_FORECAST_WORDS = (r"(mean|means|meaning|explain|explanation|how accurate|how reliable|accurate|accuracy|"
                          r"reliable|reliability|trust|method|how does it work|how is it made|range means|what does it show)")
COMPARE_WORDS = (r"(higher|lower|more|less|compare|comparison|than|normal|average|usual|typical|last year|"
                 r"before|previous|change|changed)")
MAX_FORECAST_MONTHS = 300  # January 2026 to December 2050
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_NUMBERS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}
MONTH_PATTERN = "(" + "|".join(sorted(MONTH_NUMBERS, key=len, reverse=True)) + ")"
SOURCE_FORECAST = "Weather and climate forecast (demo data)"


def wants_climate(text: str) -> bool:
    return re.search(r"\b" + CLIMATE_WORDS + r"\b", text) is not None


def wants_forecast(text: str) -> bool:
    return re.search(r"\b" + FORECAST_WORDS + r"\b", text) is not None


def wants_forecast_explanation(text: str, context: dict | None = None) -> bool:
    if re.search(r"\b" + EXPLAIN_FORECAST_WORDS + r"\b", text) is None:
        return False
    if wants_forecast(text):
        return True
    return context is not None and re.search(
        r"\b(this|that|it|data|result|results|figure|figures|value|values|number|numbers)\b", text) is not None

def wants_followup(text: str) -> bool:
    return (re.search(r"\b(that|it|this|those|same)\b", text) is not None
            or re.search(r"\b" + COMPARE_WORDS + r"\b", text) is not None)


def forecast_explanation() -> str:
    return ("A forecast here is a machine estimate of the coming months. It is not a prediction of real weather.\n"
            "The method is Holt-Winters smoothing. It follows the recent level, the trend and the yearly rhythm "
            "of the data, then continues them forward.\n"
            "The 80% range is the band the value should fall inside about 8 times in 10. Its width comes from how "
            "far past forecasts were off in the backtest. A range is only given for the first 6 months, the period "
            "the backtest tested.\n"
            "On the synthetic data the method beat a simple monthly average only for the first three months. "
            "Beyond that, the values only repeat the seasonal pattern.\n"
            "The data are SYNTHETIC demonstration values, not Meteo Rwanda observations. Do not use the forecasts "
            "for planning or reporting. Ask for a district and month to see a value.")


def _has_period(text: str) -> bool:
    """True when the question names a month, a number of months or a year."""
    return (re.search(r"\b" + MONTH_PATTERN + r"\s+20\d{2}\b", text) is not None
            or re.search(r"next \d+ months?", text) is not None
            or re.search(r"\b20\d{2}\b", text) is not None)


def forecast_horizon(text: str) -> int:
    """Months ahead of December 2025. Uses a named month and year ("july 2027"), then "next N months",
    then a bare year (December of that year). Defaults to 6 (June 2026)."""
    m = re.search(r"\b" + MONTH_PATTERN + r"\s+(20\d{2})\b", text)
    if m:
        year = int(m.group(2))
        if 2026 <= year <= 2050:
            return min((year - 2025) * 12 + MONTH_NUMBERS[m.group(1)] - 12, MAX_FORECAST_MONTHS)
    m = re.search(r"next (\d+) months?", text)
    if m:
        return max(1, min(int(m.group(1)), MAX_FORECAST_MONTHS))
    years = [int(y) for y in re.findall(r"\b(20\d{2})\b", text) if 2026 <= int(y) <= 2050]
    if years:
        return min((max(years) - 2025) * 12, MAX_FORECAST_MONTHS)
    return 6


def _calendar(horizon: int) -> tuple[int, int]:
    """(year, month) that is `horizon` months after December 2025."""
    return 2025 + (11 + horizon) // 12, (11 + horizon) % 12 + 1


def month_label(horizon: int) -> str:
    """Name of the month `horizon` months after December 2025, for example 19 gives 'Jul 2027'."""
    year, month = _calendar(horizon)
    return f"{MONTHS[month - 1]} {year}"


def _rows_by_district(db: Session) -> dict[str, list]:
    grouped = defaultdict(list)
    query = db.query(ClimateObservation).order_by(
        ClimateObservation.district, ClimateObservation.year, ClimateObservation.month)
    for r in query.all():
        grouped[r.district].append(r)
    return grouped


def forecast_answer(db: Session, district: str | None, text: str) -> tuple[str, list[str], dict | None]:
    """Returns (reply, sources, context). The context lets a follow-up question refer to this forecast."""
    years = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", text)]
    if any(y < 2026 or y > 2050 for y in years):
        return ("Forecasts cover January 2026 to December 2050. For past years, ask for the figures with a year, "
                "for example: \"rainfall in Musanze in 2022\"."), [], None

    variable = "temp" if re.search(r"\b(temperature|temperatures|temp|hot|heat)\b", text) else "rain"
    horizon = forecast_horizon(text)
    label = month_label(horizon)
    cal_year, cal_month = _calendar(horizon)
    unit = UNITS[variable]
    name = "Rainfall" if variable == "rain" else "Temperature"
    backtest = load_backtest()
    grouped = _rows_by_district(db)
    lines = []
    if not _has_period(text):
        lines.append(f"No month was given, so this shows {label}. Ask for a month, for example "
                     "\"rain forecast for july 2027\".")

    if district:
        rows = grouped.get(district, [])
        if len(rows) < MIN_MONTHS:
            return f"Not enough climate data for {district} to make a forecast.", [], None
        p = district_forecast(rows, variable, horizon, backtest)["forecast"][-1]
        lines.append(f"{name} forecast for {district}, {label}: {p['point']} {unit} "
                     "(SYNTHETIC demo data, machine estimate).")
        if horizon <= MAX_HORIZON and p["lower80"] is not None:
            lines.append(f"80% range: {p['lower80']} to {p['upper80']} {unit}. On the synthetic data this method "
                         "beat the simple monthly average only for the first three months, so treat later months "
                         "with caution.")
        else:
            lines.append("No range is given beyond 6 months, because the method has not been tested that far ahead. "
                         "The value only continues the smoothed seasonal pattern. It is not a projection of "
                         "climate change.")
        lines.append("DEMO DATA: rainfall and temperature are synthetic, not Meteo Rwanda observations.")
        context = {"district": district, "variable": variable, "month": cal_month, "year": cal_year,
                   "label": label, "point": p["point"], "unit": unit}
        return "\n".join(lines), [SOURCE_FORECAST], context

    lines.append(f"{name} forecast for {label}, all districts (SYNTHETIC demo data, machine estimate):")
    for d in sorted(grouped):
        rows = grouped[d]
        if len(rows) < MIN_MONTHS:
            continue
        p = district_forecast(rows, variable, horizon, backtest)["forecast"][-1]
        lines.append(f"{d}: {p['point']} {unit}")
    if horizon > MAX_HORIZON:
        lines.append("No ranges are given beyond 6 months. These values only continue the smoothed seasonal "
                     "pattern and are not a projection of climate change.")
    lines.append("DEMO DATA: rainfall and temperature are synthetic, not Meteo Rwanda observations.")
    context = {"district": None, "variable": variable, "month": cal_month, "year": cal_year,
               "label": label, "point": None, "unit": unit}
    return "\n".join(lines), [SOURCE_FORECAST], context


def followup_answer(db: Session, context: dict, text: str) -> tuple[str, list[str]]:
    """Answers a question about the last forecast IsokoBot gave, such as 'is that higher than normal?'."""
    district, variable = context.get("district"), context.get("variable", "rain")
    unit, label, point = UNITS[variable], context.get("label", ""), context.get("point")
    if not district or point is None:
        return ("Ask about one district first, for example \"rain forecast for Huye for july 2027\", "
                "then ask again."), []
    if re.search(r"\b" + COMPARE_WORDS + r"\b", text):
        first, last = climate.CLIMATE_YEARS[0], climate.CLIMATE_YEARS[-1]
        month = context["month"]
        rows = [r for r in db.query(ClimateObservation).filter_by(district=district).all() if r.month == month]
        if re.search(r"\blast year\b", text):
            rows = [r for r in rows if r.year == last]
            basis = f"the {MONTHS[month - 1]} value for {last}"
        else:
            basis = f"the average {MONTHS[month - 1]} value over {first} to {last}"
        if not rows:
            return f"There is no history for {district} in {MONTHS[month - 1]} to compare with.", []
        base = sum((r.rain_mm if variable == "rain" else r.temp_c) for r in rows) / len(rows)
        if not base:
            return f"The history for {district} in {MONTHS[month - 1]} is zero, so no percentage can be given.", []
        pct = (point - base) / base * 100
        direction = "above" if pct > 0 else "below" if pct < 0 else "at"
        return (f"The {label} forecast for {district} is {point} {unit}, which is {abs(pct):.0f}% {direction} "
                f"{basis}, {base:.1f} {unit}. Both are SYNTHETIC demonstration values, so this compares the demo "
                "data only."), [SOURCE_FORECAST]
    return (f"The last forecast was {label} for {district}: {point} {unit}. Ask \"what does that forecast mean?\" "
            "for how it is made, or \"is that higher than normal?\" to compare it with history."), [SOURCE_FORECAST]


def climate_answer(db: Session, district: str | None, year: int | None) -> tuple[str, list[str]]:
    first, last = climate.CLIMATE_YEARS[0], climate.CLIMATE_YEARS[-1]
    if not district:
        return ("Tell me the district and year, for example: \"rainfall in Musanze in 2022\". "
                f"Climate data covers {first} to {last}."), []
    year = year or last
    if not first <= year <= last:
        return f"No data found for {year}. Climate data covers {first} to {last}.", []
    table = climate.build_table(db.query(ClimateObservation).all())
    summary = climate.district_year(table, district, year)
    if summary is None:
        return f"No data found for {district} in {year}.", []
    direction = "above" if summary["rain_vs_normal_pct"] > 0 else "below" if summary["rain_vs_normal_pct"] < 0 else "at"
    lines = [
        f"{district}, {year}: {summary['rain_mm']:,.0f} mm of rain, "
        f"{abs(summary['rain_vs_normal_pct']):.1f}% {direction} the normal of {summary['rain_normal_mm']:,.0f} mm.",
        f"Mean temperature: {summary['temp_c']:.1f} C, {summary['temp_vs_normal_c']:+.1f} C against normal.",
        f"Farming impact: {summary['impact_label']}. {summary['impact_text']}",
        "DEMO DATA: rainfall and temperature are synthetic, not Meteo Rwanda observations.",
    ]
    return "\n".join(lines), ["Weather and climate (demo data)"]