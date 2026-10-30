"""Calculations for the Indicators map. No database access here, so each rule can be tested by hand.

Conventions
  values    : dict mapping (district, year, season) -> number. Season is "" for annual indicators.
  change    : this year minus the same district and season one year earlier.
              change_pct = change / previous x 100 (None when the previous value is 0 or missing).
  For percentage indicators the absolute change is in percentage points.
"""


def _round(x, nd=2):
    return None if x is None else round(x, nd)


def change(curr, prev):
    """Return (absolute change, percentage change). Either may be None when it cannot be worked out."""
    if curr is None or prev is None:
        return None, None
    diff = curr - prev
    pct = diff / prev * 100 if prev else None
    return _round(diff), _round(pct, 1)


def scale(value, lo, hi):
    """Scale a value to 0-100 between lo and hi. A flat range gives the midpoint, 50."""
    if hi <= lo:
        return 50.0
    return (value - lo) / (hi - lo) * 100


def snapshot_rows(values, districts, year, season):
    """One row per district for a single year and season, with the change from the year before."""
    cur = {d: values.get((d, year, season)) for d in districts}
    ranked = sorted((d for d in districts if cur[d] is not None), key=lambda d: -cur[d])
    rank = {d: i + 1 for i, d in enumerate(ranked)}
    rows = []
    for d in districts:
        prev = values.get((d, year - 1, season))
        abs_change, pct = change(cur[d], prev)
        rows.append({"name": d, "value": _round(cur[d]), "prev_value": _round(prev),
                     "change_abs": abs_change, "change_pct": pct, "rank": rank.get(d)})
    return rows


def national_summary(values, districts, year, season):
    """Average across the districts that reported, plus the average change across districts that
    reported both this year and the year before (so the change compares like with like)."""
    cur = [values[(d, year, season)] for d in districts if (d, year, season) in values]
    both = [(values[(d, year, season)], values[(d, year - 1, season)]) for d in districts
            if (d, year, season) in values and (d, year - 1, season) in values]
    out = {"districts_reporting": len(cur), "mean_value": _round(sum(cur) / len(cur)) if cur else None,
           "districts_comparable": len(both), "mean_change_abs": None, "mean_change_pct": None}
    if both:
        mean_now = sum(c for c, _ in both) / len(both)
        mean_before = sum(p for _, p in both) / len(both)
        abs_change, pct = change(mean_now, mean_before)
        out.update({"mean_change_abs": abs_change, "mean_change_pct": pct})
    return out


def food_security(annual, pillars):
    """Food security score for every district-year that has a value for every pillar.

    annual  : {indicator key: {(district, year): value}} for annual indicators only
    pillars : {pillar name: [indicator keys]}. A pillar with several keys uses their plain average,
              and only district-years where all of them are present are scored.
    Returns {(district, year): {"score": x, "pillars": {pillar: {"raw": r, "scaled": s}}}}.
    """
    if not pillars:
        return {}
    raw = {}
    for pillar, keys in pillars.items():
        series = [annual.get(k, {}) for k in keys]
        common = set.intersection(*(set(s) for s in series))
        raw[pillar] = {dy: sum(s[dy] for s in series) / len(series) for dy in common}
    bounds = {p: (min(v.values()), max(v.values())) for p, v in raw.items() if v}
    complete = set.intersection(*(set(raw[p]) for p in pillars))
    out = {}
    for dy in sorted(complete):
        parts = {}
        for pillar in pillars:
            lo, hi = bounds[pillar]
            parts[pillar] = {"raw": _round(raw[pillar][dy]), "scaled": _round(scale(raw[pillar][dy], lo, hi), 1)}
        score = sum(parts[p]["scaled"] for p in pillars) / len(pillars)
        out[dy] = {"score": _round(score, 1), "pillars": parts}
    return out
