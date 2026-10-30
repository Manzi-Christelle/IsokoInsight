# Data source register



| Dataset | Publisher | Period | URL | Downloaded | Processing | Status |
|---|---|---|---|---|---|---|
| Consumer Price Index, All Rwanda (monthly, Feb 2009 to Aug 2026, base Feb 2014 = 100, 18 series) | NISR | Feb 2009 to Aug 2026 | https://statistics.gov.rw (file CPI_time_series_August_2026.xls, Table D 'All Rwanda') | 2026-10-29 (file received from the team) | Exported to app/data/cpi/nisr_cpi_all_rwanda_2009_2026.csv with NISR series codes kept; loaded by app/seed.py. Headline year-on-year inflation is calculated from the general index, not typed in. | Done. Checked against the NISR file: Aug 2026 general index 241.37, year-on-year 15.9%; Jul 2026 13.8% |
| Rainfall and temperature, Rwanda | Meteo Rwanda | n/a | https://www.meteorwanda.gov.rw ; data portal and climate data request linked from that site | n/a | Not used yet. The data portal disallows automated access (robots.txt), we requested access but we didn't receive a confirmation. Our last option was to synthesize the data.| 
| District boundaries, Rwanda ADM2 (30 districts) | geoBoundaries gbOpen (William & Mary geoLab), licence CC BY 4.0 | current release | https://www.geoboundaries.org (file fetched from the geoBoundaries GitHub repository, 2026-10-23) | 2026-10-23 | Polygon simplified (tolerance 0.002 degrees) and coordinates rounded to 4 decimals for the web; `shapeName` kept as district name. Output: app/static/data/rwanda_districts.geojson | Done. Attribution shown in the app footer and map |
| Seasonal Agriculture Survey | NISR |  |
| Market price observations | n/a | n/a | unit standardised | 
| DEMO synthetic prices and CPI | generated | n/a | n/a | n/a | n/a | 

| Climate forecast backtest results (derived from the DEMO rainfall and temperature data) | Calculated by the project (app/ml/forecast_climate.py) | Forecast origins every 3 months from 2019 (810 per measure) | n/a | Not applicable (calculated, not downloaded) | Saved to app/ml/artifacts/climate_backtest.json and shown in the forecast panel and docs/MACHINE_LEARNING.md. Labelled demo. | Labelled DEMO. Recalculate after the real rainfall data is loaded (see the Meteo Rwanda row). |
| IsokoBot question-classifier training and test questions (256 templates, 1,304 examples, 34 challenge questions, 16 intents) | Written by our team | n/a | n/a | Not applicable (author-written text, not an external dataset) | Trains the fallback intent classifier (app/ml/intent_data.py and app/ml/intent_classifier.py).
 Evaluation in docs/CHATBOT_CLASSIFIER_EVALUATION.md | Written by the authors. External test questions still to be collected. |

## District indicator workbooks (app/data/indicators/)

| File | Indicator(s) | Years | Status |
|---|---|---|---|
| rwanda_households_within_1km_market_SYNTHETIC_DEMO.xlsx | Households within 1 km of a market (%) | 2000-2025 | SYNTHETIC DEMO |
| rwanda_grain_reserve_SYNTHETIC_DEMO.xlsx | Grain held in reserve (thousand kg) | 2000-2025 | SYNTHETIC DEMO |
| rwanda_households_livestock_SYNTHETIC_DEMO.xlsx | Cattle, goats, chickens, pigs, rabbits, sheep kept (% of households) | 2000-2025 | SYNTHETIC DEMO |
| rwanda_agri_inputs_SYNTHETIC_DEMO.xlsx (district sheets) | Improved seeds, inorganic and organic fertilizer, pesticides (% of farmers, seasons A-C) | 2021-2026 | SYNTHETIC DEMO |
| rwanda_agri_inputs_SYNTHETIC_DEMO.xlsx (National sheet) | National input figures, each row citing its source | 2023-2026 | Recorded, not re-checked |

The workbook READMEs state that the district values are randomly generated and must not be used for analysis or reporting. Every screen and API response that shows them carries a label. Replace them with the real NISR survey tables (for example CFSVA and the Seasonal Agricultural Survey) before any real use.
