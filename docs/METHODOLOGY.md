# Methodology

1. **Two streams, kept apart.** Official NISR CPI (national indices) and local market observations (item prices). The interface labels each, and no calculation mixes them.
2. **Cleaning (CPI).** Encoding normalised (UTF-8, then Windows-1252, then Latin-1), title and footer rows removed, weights converted from text such as " 10,000 " to numbers, month labels parsed to the first day of the month.
3. **Changes.** % change = (new - reference) / reference x 100. Month-on-month uses the previous month; year-on-year uses the same month of the previous year.
4. **Market comparison.** Latest VERIFIED price per market, per unit; difference vs the cheapest market. Units are never mixed.
5. **District colours (district map).**
   - Keep the latest verified price per product, unit and market.
   - National reference = median of those prices for the same product and unit, where at least two markets report that product.
   - Deviation per product = (market price - national reference) / national reference x 100.
   - District index = unweighted mean of the deviations of the products reported in that district.
   - **Critical (red)** if index > 15%; **medium (yellow)** if index > 5% and up to 15%; **good (green)** if index is 5% or less.
   - **Grey**: no verified data, or fewer than 2 products (`limited_data`).
   - Thresholds are configurable (`DISTRICT_YELLOW_PCT`, `DISTRICT_RED_PCT`, `DISTRICT_MIN_PRODUCTS`).
   - Limits: one market per district means the colour reflects that market only. The index uses equal weights for products, not household spending weights. A colour does not measure incomes, access or shortages.
6. **Review flags.** A change is flagged if it is at or above a configurable threshold (CPI 5% monthly; submitted prices 25% vs last verified), or if its robust z-score (median/MAD) is 3.5 or more. A flag requests human review. It does not state a cause.
7. **Verification.** Submissions start `pending`, appear publicly only after an administrator approves or corrects them, and every decision is logged (who, when, old and new value, note).
8. **IsokoBot.** A rule-based assistant. It reads only verified prices, the district colours and the recorded NISR figures. It never generates numbers outside these tables, it never quotes pending submissions, and it labels synthetic demo data.
9. **Limits.** No price prediction is claimed. Results depend on the quality and coverage of the data loaded. Demo data is synthetic.

## District indicators and the food security score (v5)

**Year change.** For every district, indicator and season, the change is this year's value minus the value for the same district and season one year earlier. The percentage change is that difference divided by the earlier value, and is blank when the earlier value is zero. For percentage indicators the absolute change is in percentage points.

**National summary.** The average is taken across the districts that reported. The average change compares only the districts that reported both years.

**Food security score (0 to 100), by district and year.** The score is the equal-weighted average of three pillars:
1. Market access: households within 1 km of a market (%).
2. Stock: grain held in reserve (thousand kg).
3. Assets: the plain average of the six livestock indicators (cattle, goats, chickens, pigs, rabbits, sheep; % of households).

Each pillar is scaled from 0 to 100 between the lowest and highest district-year value for that pillar across the whole 2000-2025 panel. Because the scale is fixed across years, a rise in the score means a real improvement, not a change in rank. A district-year is scored only when all three pillars are present.

**What the score is not.** It is a relative index for illustration. It does not measure hunger, nutrition or household income, and it is not an official NISR measure. Agricultural input use (2021-2026) is shown on its own and is not part of the score, because it covers fewer years and is seasonal.

**Data status.** The four district workbooks are synthetic demonstration data, so the score built from them is synthetic too. The national agricultural input figures are recorded from the sources named in each row and have not been re-checked. Before any analysis or submission, replace the workbooks with the real NISR tables and recalculate.

## Weather and climate (synthetic demo)

Rainfall and temperature are generated for the prototype, not observed. Normal rainfall is a district's
average annual total over 2016 to 2025. Rainfall vs normal = (year total - normal) / normal x 100.
Impact classes: 20% or more below normal (severe dry), 10% to 20% below (dry), within 10% (normal),
10% to 20% above (wet), 20% or more above (very wet flood risk). Temperature vs normal is the year's
mean minus the district's baseline mean; 0.8 C or more above normal adds a heat-stress note.

## District price map (demo)

For one product: the latest verified price at each market, averaged within each district. Districts are
banded into five equal steps between the cheapest and dearest district averages.
