"""Transparent calculations. Pure functions so they are easy to test and explain.

Formulas (documented in docs/METHODOLOGY.md):
  % change   = (P_t - P_ref) / P_ref * 100
  vs cheapest = (P_market - P_cheapest) / P_cheapest * 100
  Flag rule  = |monthly change| >= threshold  OR  robust z-score >= 3.5
  robust z   = 0.6745 * (x - median) / MAD
"""
from datetime import date
from statistics import median


def pct_change(new: float, old: float) -> float | None:
    if old is None or old == 0 or new is None:
        return None
    return (new - old) / old * 100.0


def add_changes(points: list[tuple[date, float]]) -> list[dict]:
    """Attach month-on-month and year-on-year % change to a sorted (period, value) list."""
    points = sorted(points)
    by_period = {p: v for p, v in points}
    out = []
    for i, (period, value) in enumerate(points):
        mom = pct_change(value, points[i - 1][1]) if i > 0 else None
        prev_year = date(period.year - 1, period.month, 1)
        yoy = pct_change(value, by_period[prev_year]) if prev_year in by_period else None
        out.append({"period": period.isoformat(), "value": round(value, 2),
                    "mom_pct": None if mom is None else round(mom, 2),
                    "yoy_pct": None if yoy is None else round(yoy, 2)})
    return out


def detect_series_anomalies(points: list[tuple[date, float]], threshold_pct: float,
                            z_threshold: float = 3.5) -> list[dict]:
    """Return months whose change is unusually large. These are REVIEW FLAGS only."""
    points = sorted(points)
    changes = []
    for i in range(1, len(points)):
        c = pct_change(points[i][1], points[i - 1][1])
        if c is not None:
            changes.append((points[i][0], c))
    if len(changes) < 6:
        return []
    values = [c for _, c in changes]
    med = median(values)
    mad = median(abs(v - med) for v in values)
    flags = []
    for period, c in changes:
        reasons = []
        if abs(c) >= threshold_pct:
            reasons.append(f"monthly change {c:+.1f}% is at or above the {threshold_pct:g}% threshold")
        if mad > 0:
            z = 0.6745 * (c - med) / mad
            if abs(z) >= z_threshold:
                reasons.append(f"robust z-score {z:+.1f} (unusual compared with the series history)")
        if reasons:
            flags.append({"period": period, "change_pct": round(c, 2), "reasons": reasons})
    return flags


def compare_markets(observations: list) -> dict:
    """Compare the latest VERIFIED price per market, grouped by unit.

    Different units are never mixed: each unit gets its own comparison group.
    `observations` are PriceObservation-like objects (market, price_rwf, unit, observed_on, status).
    """
    latest: dict[tuple[str, int], object] = {}
    for o in observations:
        if o.status != "verified":
            continue
        key = (o.unit, o.market_id)
        if key not in latest or o.observed_on > latest[key].observed_on:
            latest[key] = o
    groups: dict[str, list] = {}
    for (unit, _), o in latest.items():
        groups.setdefault(unit, []).append(o)
    result = {}
    for unit, items in groups.items():
        items.sort(key=lambda o: o.price_rwf)
        cheapest = items[0].price_rwf
        rows = []
        for o in items:
            diff = pct_change(o.price_rwf, cheapest)
            rows.append({
                "market_id": o.market_id, "market": o.market.name, "district": o.market.district,
                "price_rwf": o.price_rwf, "observed_on": o.observed_on.isoformat(),
                "diff_rwf": o.price_rwf - cheapest,
                "diff_pct_vs_cheapest": None if diff is None else round(diff, 1),
                "is_synthetic": o.is_synthetic,
            })
        result[unit] = {"markets_compared": len(rows), "cheapest_market": rows[0]["market"],
                        "rows": rows}
    return result


def district_status(observations: list, district_names: list[str], yellow_pct: float = 5.0,
                    red_pct: float = 15.0, min_products: int = 2) -> list[dict]:
    """Colour-code every district by how its food prices compare with the national median.

    Method (documented in docs/METHODOLOGY.md):
      1. Keep the latest VERIFIED price per (product, unit, market).
      2. National reference = median of those prices for the same product and unit
         (only where at least 2 markets report that product).
      3. Deviation per product = (market price - national reference) / national reference x 100.
      4. District index = unweighted mean of the deviations of the products reported in that district.
      5. Status: critical (red) if index > red_pct; medium (yellow) if index > yellow_pct;
         good (green) otherwise. Fewer than min_products -> limited_data (grey).
         No verified prices at all -> no_data (grey).
    `observations` are PriceObservation-like objects with market, product, unit, price_rwf,
    observed_on, status and is_synthetic loaded.
    """
    latest: dict[tuple[int, str, int], object] = {}
    for o in observations:
        if o.status != "verified":
            continue
        key = (o.product_id, o.unit, o.market_id)
        if key not in latest or o.observed_on > latest[key].observed_on:
            latest[key] = o

    by_product_unit: dict[tuple[int, str], list] = {}
    for (pid, unit, _), o in latest.items():
        by_product_unit.setdefault((pid, unit), []).append(o)
    reference = {k: median(o.price_rwf for o in items)
                 for k, items in by_product_unit.items() if len(items) >= 2}

    acc: dict[str, dict] = {}
    for (pid, unit, _), o in latest.items():
        if (pid, unit) not in reference:
            continue
        ref = reference[(pid, unit)]
        dev = (o.price_rwf - ref) / ref * 100.0
        entry = acc.setdefault(o.market.district, {"details": [], "markets": set(),
                                                   "dates": [], "synthetic": False})
        entry["details"].append({"product": o.product.name, "unit": unit, "market": o.market.name,
                                 "price_rwf": o.price_rwf,
                                 "national_median_rwf": round(ref),
                                 "deviation_pct": round(dev, 1),
                                 "observed_on": o.observed_on.isoformat()})
        entry["markets"].add(o.market.name)
        entry["dates"].append(o.observed_on)
        entry["synthetic"] = entry["synthetic"] or o.is_synthetic

    results = []
    for name in district_names:
        e = acc.get(name)
        if not e:
            results.append({"name": name, "status": "no_data", "index_pct": None, "products_used": 0,
                            "markets": [], "latest_date": None, "details": [], "contains_synthetic": False})
            continue
        index = sum(d["deviation_pct"] for d in e["details"]) / len(e["details"])
        n = len(e["details"])
        if n < min_products:
            status = "limited_data"
        elif index > red_pct:
            status = "critical"
        elif index > yellow_pct:
            status = "medium"
        else:
            status = "good"
        results.append({"name": name, "status": status, "index_pct": round(index, 1),
                        "products_used": n, "markets": sorted(e["markets"]),
                        "latest_date": max(e["dates"]).isoformat(),
                        "details": sorted(e["details"], key=lambda d: d["product"]),
                        "contains_synthetic": e["synthetic"]})
    return results


def summary_by_product(observations: list) -> list[dict]:
    """Statistics per product and unit, from the latest verified price in each market."""
    latest: dict[tuple[int, str, int], object] = {}
    for o in observations:
        if o.status != "verified":
            continue
        key = (o.product_id, o.unit, o.market_id)
        if key not in latest or o.observed_on > latest[key].observed_on:
            latest[key] = o
    groups: dict[tuple[str, str], list] = {}
    for o in latest.values():
        groups.setdefault((o.product.name, o.unit), []).append(o)
    out = []
    for (name, unit), items in sorted(groups.items()):
        prices = [o.price_rwf for o in items]
        out.append({"product": name, "unit": unit, "markets": len(items),
                    "min_rwf": min(prices), "median_rwf": round(median(prices)), "max_rwf": max(prices),
                    "latest_date": max(o.observed_on for o in items).isoformat(),
                    "contains_synthetic": any(o.is_synthetic for o in items)})
    return out


def monthly_medians(observations: list) -> list[dict]:
    """Median verified price per product, unit and calendar month (all verified observations)."""
    buckets: dict[tuple[str, str, str], list] = {}
    for o in observations:
        if o.status != "verified":
            continue
        month = o.observed_on.strftime("%Y-%m")
        buckets.setdefault((o.product.name, o.unit, month), []).append(o)
    out = []
    for (name, unit, month), items in sorted(buckets.items()):
        out.append({"product": name, "unit": unit, "month": month, "observations": len(items),
                    "median_rwf": round(median(o.price_rwf for o in items)),
                    "contains_synthetic": any(o.is_synthetic for o in items)})
    return out
