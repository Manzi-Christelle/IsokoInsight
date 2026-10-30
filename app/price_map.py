"""Compare one product's verified prices across districts.

For each district: the latest verified price at each market in the district, then the district average.
Colour bands are five equal steps between the cheapest and the dearest district average.
Districts without a market that has verified this product are left uncoloured.
"""
import math
from statistics import mean

BAND_COUNT = 5


def district_prices(obs: list, district_names: list[str]) -> dict:
    """obs: PriceObservation-like objects with market, unit, price_rwf, observed_on, status, is_synthetic."""
    latest: dict[tuple[int, str], object] = {}
    for o in obs:
        if o.status != "verified":
            continue
        key = (o.market_id, o.unit)
        if key not in latest or o.observed_on > latest[key].observed_on:
            latest[key] = o

    by_district: dict[str, list] = {}
    for o in latest.values():
        by_district.setdefault(o.market.district, []).append(o)

    rows = []
    for name in sorted(district_names):
        items = by_district.get(name, [])
        if not items:
            rows.append({"name": name, "average_rwf": None, "min_rwf": None, "max_rwf": None,
                         "markets": [], "markets_count": 0, "latest_date": None,
                         "contains_synthetic": False, "band": None, "vs_cheapest_pct": None})
            continue
        prices = [o.price_rwf for o in items]
        rows.append({
            "name": name,
            "average_rwf": round(mean(prices)),
            "min_rwf": min(prices), "max_rwf": max(prices),
            "markets": [{"market": o.market.name, "price_rwf": o.price_rwf,
                         "observed_on": o.observed_on.isoformat(), "is_synthetic": o.is_synthetic}
                        for o in sorted(items, key=lambda x: x.price_rwf)],
            "markets_count": len(items),
            "latest_date": max(o.observed_on for o in items).isoformat(),
            "contains_synthetic": any(o.is_synthetic for o in items),
            "band": None, "vs_cheapest_pct": None,
        })

    priced = [r for r in rows if r["average_rwf"] is not None]
    edges: list[float] = []
    cheapest = highest = None
    spread = None
    if priced:
        lo = min(r["average_rwf"] for r in priced)
        hi = max(r["average_rwf"] for r in priced)
        cheapest = min(priced, key=lambda r: r["average_rwf"])["name"]
        highest = max(priced, key=lambda r: r["average_rwf"])["name"]
        spread = round((hi - lo) / lo * 100.0, 1) if lo else None
        edges = [round(lo + (hi - lo) * k / BAND_COUNT) for k in range(BAND_COUNT + 1)]
        for r in priced:
            if hi <= lo:
                r["band"] = 2
            else:
                r["band"] = min(BAND_COUNT - 1, math.floor((r["average_rwf"] - lo) / (hi - lo) * BAND_COUNT))
            r["vs_cheapest_pct"] = round((r["average_rwf"] - lo) / lo * 100.0, 1) if lo else None

    return {
        "districts": rows,
        "districts_with_prices": len(priced),
        "cheapest_district": cheapest,
        "highest_district": highest,
        "spread_pct": spread,
        "band_edges_rwf": edges,
        "bands": BAND_COUNT,
        "as_of": max((r["latest_date"] for r in rows if r["latest_date"]), default=None),
        "contains_synthetic": any(r["contains_synthetic"] for r in rows),
    }
