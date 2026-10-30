"""Reference catalogue of products and markets.

The first six products and the first four markets are the original demo set. Everything after them
is an addition. The overall district colours use only the six staple products (CORE_PRODUCT_NAMES),
so adding products does not change the figures that were already shown.
"""

# name, category, standard unit
PRODUCTS = [
    ("Irish potatoes", "Tubers", "kg"),
    ("Maize flour", "Cereals", "kg"),
    ("Dry beans", "Pulses", "kg"),
    ("Tomatoes", "Vegetables", "kg"),
    ("Rice", "Cereals", "kg"),
    ("Cooking oil", "Oils and fats", "litre"),
    # Additions: common market goods by group
    ("Beef", "Meat", "kg"),
    ("Goat meat", "Meat", "kg"),
    ("Fresh milk", "Dairy", "litre"),
    ("Bananas", "Fruits", "kg"),
    ("Avocados", "Fruits", "kg"),
    ("Cabbage", "Vegetables", "kg"),
    ("Onions", "Vegetables", "kg"),
    ("Wheat flour", "Cereals", "kg"),
]

# name, district
MARKETS = [
    ("Kimironko Market", "Gasabo"),
    ("Nyabugogo Market", "Nyarugenge"),
    ("Musanze Market", "Musanze"),
    ("Huye Market", "Huye"),
    # Additions: one market in each of the other provinces
    ("Rubavu Market", "Rubavu"),
    ("Nyagatare Market", "Nyagatare"),
    ("Muhanga Market", "Muhanga"),
    ("Rusizi Market", "Rusizi"),
]

# Demonstration markets: every district without a listed market gets one synthetic market, so the
# product maps can colour all 30 districts. These markets price all 14 products (synthetic values).
from .climate import DISTRICT_PROVINCE  # noqa: E402  (30 district names)
_covered = {d for _, d in MARKETS}
MARKETS = MARKETS + [(f"{d} Market", d) for d in sorted(DISTRICT_PROVINCE) if d not in _covered]

CORE_PRODUCT_NAMES = [p[0] for p in PRODUCTS[:6]]
CORE_MARKET_NAMES = [m[0] for m in MARKETS[:4]]
ADDED_MARKET_NAMES = [m[0] for m in MARKETS[4:]]
