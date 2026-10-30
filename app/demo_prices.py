"""Synthetic demonstration prices, from January 2000 to August 2026.

Every (product, market) pair gets one price per month, on the 15th. The values are built from fixed
rules: a base price per product, a market factor, a yearly trend, a small seasonal pattern and a little
noise. Each value depends only on the product, the market and the month, so re-seeding gives the same
numbers. Every row is marked is_synthetic=True. These are NOT real Rwandan prices.
"""
import math
import zlib
from collections.abc import Iterator
from datetime import date

DEMO_FIRST_MONTH = (2000, 1)
DEMO_LAST_MONTH = (2026, 8)
ANNUAL_TREND = 0.08          # prices are stepped back from early 2026 at 8% a year
BASE_YEAR = 2026 + 2 / 12    # the base prices are for March 2026

# Base price in RWF per unit, for March 2026
BASE_PRICE = {"Irish potatoes": 450, "Maize flour": 800, "Dry beans": 1100, "Tomatoes": 700,
              "Rice": 1300, "Cooking oil": 2800,
              "Beef": 4200, "Goat meat": 4800, "Fresh milk": 500, "Bananas": 400, "Avocados": 600,
              "Cabbage": 300, "Onions": 900, "Wheat flour": 1200}


def demo_months() -> list[date]:
    """The 15th of every month from the first to the last demo month, inclusive."""
    y, m = DEMO_FIRST_MONTH
    out = []
    while (y, m) <= DEMO_LAST_MONTH:
        out.append(date(y, m, 15))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _stable_fraction(key: str) -> float:
    """A fixed number between 0 and 1 for a text key (no randomness, the same on every run)."""
    return (zlib.crc32(key.encode("utf-8")) % 10_000) / 10_000


def market_factor(market_name: str) -> float:
    return 0.9 + 0.25 * _stable_fraction("market|" + market_name)


def demo_price(product_name: str, market_name: str, day: date) -> int:
    """Price in whole RWF for one product at one market on one day."""
    base = BASE_PRICE[product_name]
    years_from_base = (day.year + (day.month - 0.5) / 12) - BASE_YEAR
    trend = (1 + ANNUAL_TREND) ** years_from_base
    phase = 2 * math.pi * _stable_fraction("season|" + product_name)
    seasonal = 1 + 0.03 * math.sin(2 * math.pi * day.month / 12 + phase)
    noise = 0.97 + 0.06 * _stable_fraction(f"{product_name}|{market_name}|{day.isoformat()}")
    return int(round(base * market_factor(market_name) * trend * seasonal * noise))


def demo_price_rows(products, markets, source_id: int, chunk: int = 5000) -> Iterator[list[dict]]:
    """Yield the demo observations in chunks, ready for a bulk insert.

    products and markets are model rows (or anything with .id, .name and .standard_unit / .district).
    """
    months = demo_months()
    batch: list[dict] = []
    for product in products:
        for market in markets:
            for day in months:
                batch.append({"product_id": product.id, "market_id": market.id,
                              "price_rwf": demo_price(product.name, market.name, day),
                              "unit": product.standard_unit, "observed_on": day,
                              "collection_method": "synthetic demo", "source_id": source_id,
                              "status": "verified", "is_synthetic": True})
                if len(batch) >= chunk:
                    yield batch
                    batch = []
    if batch:
        yield batch


def expected_demo_rows(n_products: int, n_markets: int) -> int:
    return n_products * n_markets * len(demo_months())
