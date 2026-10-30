"""Catalogue of the district indicators shown on the Indicators map.

Each indicator is one sheet in one of the workbooks in app/data/indicators/. The food security
score is not a workbook: it is calculated from three of the indicators (see SCORE_PILLARS).

All four workbooks are SYNTHETIC DEMONSTRATION DATA. Their README sheets say they are not NISR or
census statistics and must not be used for analysis or reporting. Every screen that shows them says so.
"""
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data" / "indicators"

# Name used for the national row in the agricultural inputs 'National' sheet.
NATIONAL = "Rwanda (national)"

WORKBOOKS = {
    "access": "rwanda_households_within_1km_market_SYNTHETIC_DEMO.xlsx",
    "grain": "rwanda_grain_reserve_SYNTHETIC_DEMO.xlsx",
    "livestock": "rwanda_households_livestock_SYNTHETIC_DEMO.xlsx",
    "inputs": "rwanda_agri_inputs_SYNTHETIC_DEMO.xlsx",
}

SOURCE_NAMES = {
    "access": "DEMO - households within 1 km of a market (synthetic)",
    "grain": "DEMO - grain held in reserve by district (synthetic)",
    "livestock": "DEMO - livestock kept by district (synthetic)",
    "inputs": "DEMO - agricultural inputs by district and season (synthetic)",
}
NATIONAL_SOURCE = "NISR SAS - national agricultural input figures (as recorded in the workbook)"

GROUP_TITLES = {
    "access": "Market access",
    "grain": "Grain reserve",
    "livestock": "Livestock kept",
    "inputs": "Agricultural inputs used",
    "score": "Food security score",
}


@dataclass(frozen=True)
class Indicator:
    key: str
    label: str
    group: str
    unit: str
    sheet: str = ""          # worksheet name in the workbook
    seasonal: bool = False   # True when the survey reports seasons A, B and C
    description: str = ""


INDICATORS = [
    Indicator("within_1km", "Households within 1 km of a market", "access", "% of households",
              "Within_1km_market", description="Share of households living within 1 km of a market."),
    Indicator("grain_reserve", "Grain held in reserve", "grain", "thousand kg", "Grain_reserve",
              description="Quantity of grain held in reserve in the district."),
    Indicator("cows", "Cattle (cows) kept", "livestock", "% of households", "Cows",
              description="Share of households keeping cattle."),
    Indicator("goats", "Goats kept", "livestock", "% of households", "Goats",
              description="Share of households keeping goats."),
    Indicator("chickens", "Chickens kept", "livestock", "% of households", "Chickens",
              description="Share of households keeping chickens."),
    Indicator("pigs", "Pigs kept", "livestock", "% of households", "Pigs",
              description="Share of households keeping pigs."),
    Indicator("rabbits", "Rabbits kept", "livestock", "% of households", "Rabbits",
              description="Share of households keeping rabbits."),
    Indicator("sheep", "Sheep kept", "livestock", "% of households", "Sheep",
              description="Share of households keeping sheep."),
    Indicator("improved_seeds", "Improved seeds used", "inputs", "% of farmers", "Improved_seeds",
              seasonal=True, description="Share of farmers using improved seeds in the season."),
    Indicator("inorganic_fertilizer", "Inorganic fertilizer used", "inputs", "% of farmers",
              "Inorganic_fertilizer", seasonal=True,
              description="Share of farmers using inorganic fertilizer in the season."),
    Indicator("organic_fertilizer", "Organic fertilizer used", "inputs", "% of farmers",
              "Organic_fertilizer", seasonal=True,
              description="Share of farmers using organic fertilizer in the season."),
    Indicator("pesticides", "Pesticides used", "inputs", "% of farmers", "Pesticides", seasonal=True,
              description="Share of farmers using pesticides in the season."),
]

LIVESTOCK_KEYS = [i.key for i in INDICATORS if i.group == "livestock"]

FOOD_SECURITY = "food_security"
SCORE_ITEM = Indicator(
    FOOD_SECURITY, "Food security score (0 to 100)", "score", "score (0 to 100)",
    description="Higher means more food secure, relative to the lowest and highest district-year "
                "in 2000-2025. Average of three pillars, each scaled 0 to 100.")

# The score is the equal-weighted average of three pillars. Each pillar is scaled 0-100 between the
# lowest and highest district-year value for that pillar across the whole 2000-2025 panel, so a rise in
# the score means a real improvement, not a change in rank. All three pillars: higher is better.
SCORE_PILLARS = {
    "access": ["within_1km"],
    "stock": ["grain_reserve"],
    "assets": LIVESTOCK_KEYS,
}
PILLAR_LABELS = {
    "access": "Market access (households within 1 km of a market)",
    "stock": "Grain held in reserve",
    "assets": "Livestock kept (average of the six types)",
}

# Header text in the 'National' sheet of the agricultural inputs workbook -> indicator key.
NATIONAL_COLUMNS = {
    "Improved seeds (%)": "improved_seeds",
    "Inorganic fertilizer (%)": "inorganic_fertilizer",
    "Organic fertilizer (%)": "organic_fertilizer",
    "Pesticides (%)": "pesticides",
}

ALL_ITEMS = INDICATORS + [SCORE_ITEM]
BY_KEY = {i.key: i for i in ALL_ITEMS}
