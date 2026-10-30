# AagricultureInsight Rwanda - Food security Monitoring

NISR 2026 Big Data Hackathon entry. Track 1 (Agricultural Productivity) with elements of Track 3 (Open Innovation).

AgricultureInsight shows where food prices are high in Rwanda and gives a plain-language answer to questions about them. It keeps two kinds of information apart:

- **Official NISR statistics**: national Consumer Price Index (CPI) figures and headline inflation, as published by NISR.
- **Verified local market prices**: item prices collected at markets, shown only after an administrator has checked them.

## What the app shows

| Tab | What a user can do |
|---|---|
| Overview | See headline inflation and the CPI trend. Choose a category and view year-on-year change, month-on-month change or index level. Review flags highlight unusual monthly moves. |
| Market prices | Filter verified prices by product, market and date. View a price-history chart. Download the results as CSV. |
| **Compare and map** | Colour all 30 districts: **red = critical zone**, **yellow = medium**, **green = good**, **grey = no verified data**. Choose a product and press "Compare and colour map" to recolour the districts by that product's price and list each district's market price, cheapest first. "Show overall colours" returns to the overall view. Click a district for details. |
| Account | Sign in, or create an account and choose your role (see below). Page: `/account`. |
| Contribute | Farmers, sellers and enumerators submit prices and see the status of their own submissions. |
| NISR data | NISR statisticians download the full dataset (including pending and rejected records) and generate statistics. |
| Review | Administrators approve, correct or reject submissions, manage accounts, and see the audit trail. |
| Sources | Source register with publisher, period, download date and processing for every dataset. |
| **Ask AgricultureBot** (button, bottom right) | Ask questions in plain language, for example "Which districts are in the critical zone?", "Price of maize flour in Huye" or "What is headline inflation?". |

### How the district colours work
1. For each product and unit, the **national median** is the median of the latest verified price across markets.
2. Each market's latest verified price is compared with that median, giving a % difference.
3. A district's **index** is the average of those % differences across its products.
4. **Red (critical)** if the index is above 15%; **yellow (medium)** if above 5% up to 15%; **green (good)** up to 5%.
5. Grey means no verified data, or fewer than 2 products (too little to colour fairly).

The thresholds are set in `app/config.py` and explained in `docs/METHODOLOGY.md`. A colour is a prompt for attention, not proof of a shortage.

### How AgricultureBot works
IsokoBot answers only from the app's database and recorded NISR figures. It does not guess. Every answer names its sources, pending submissions are never quoted, and synthetic demo data is always labelled. It understands English and common Kinyarwanda product names (for example *ibigori* for maize, *ibirayi* for potatoes, *amavuta* for cooking oil). The Kinyarwanda terms still need checking by a native speaker.

## Accounts and roles
Anyone can read the public dashboard without an account. Accounts add the following roles (full matrix in `docs/ACCESS_CONTROL.md`):

| Role | Who | Sign-up |
|---|---|---|
| Customer | Buyers and people following prices | Approved at once |
| Farmer / seller | Report market prices and track their status | Approved at once |
| Enumerator | Field data collectors for the statistics team | Needs administrator approval |
| NISR statistician | Export the full dataset and generate statistics | Needs administrator approval |
| Administrator | Verifies prices, manages accounts, imports CPI | Created by the seed command only |

Every permission is checked on the server. Administrators approve or disable accounts and change roles on the Review tab, and a change takes effect on the person's next request.

## Data sources
See the in-app **Sources** tab and `docs/DATA_SOURCES.md`.

- **NISR CPI time series, All Rwanda (February 2009 to August 2026)**: the real NISR file, loaded from `app/data/cpi/`. Headline year-on-year inflation is calculated from the general index, so it is not typed in by hand.
- **District boundaries**: geoBoundaries gbOpen, Rwanda ADM2 (CC BY 4.0, www.geoboundaries.org). Simplified for the web and included in `app/static/data/rwanda_districts.geojson`.
- **Demo data**: `python -m app.seed --demo` loads **synthetic** prices and CPI so the interface can be shown. They are **not** real figures and are labelled in the app. Remove them with `python -m app.seed --purge-demo` before judging.

> **Status:** the real NISR CPI file and real enumerator market prices are **not yet loaded**. Until they are, the market prices, district colours and CPI categories show synthetic demo values.

## Run locally (no database server needed)

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate        macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env   (then set ADMIN_PASSWORD)
python -m app.seed --demo
uvicorn app.main:app --reload
```
Open http://localhost:8000 (dashboard) and http://localhost:8000/docs (API documentation).
The admin account is the `ADMIN_EMAIL` / `ADMIN_PASSWORD` in your `.env`.

## Run with PostgreSQL (Docker Desktop)
```bash
docker compose up --build
```

## Tests
```bash
python -m pytest -q
```
37 tests cover the calculations (including the colour rules and their boundaries), the API, the review workflow, CSV import and the chatbot's grounding.

## Demo video
`demo/demo.webm` (3 minutess): a walkthrough of the overview, market prices, comparison, the district map, weather and climate, IsokoBot and login sample.

## Submission details
- Public GitHub repository: https://github.com/Manzi-Christelle/IsokoInsight.git
- Deployed app: https://agricultureinsight-rwanda.onrender.com/

## Team and student eligibility
- Team: MUCYO MANZI Marie Christelle (team leader) and MUGISHA Kevin.
- Both members are Rwandan undergraduate students at the Adventist University of Central Africa (AUCA), Software Engineering, Gishushu campus.
- Student cards (student eligibility documents, required by the competition rules): [`student_cards/christelle_student_card.pdf`](student_cards/christelle_student_card.pdf) and [`student_cards/kevin_student_card.pdf`](student_cards/kevin_student_card.pdf). See `student_cards/README.md`.
- AI use disclosure and member declarations: [`docs/AI_DISCLOSURE.md`](docs/AI_DISCLOSURE.md).

## Machine-learning additions (version 12)

- **Rainfall and temperature forecasts** on the Weather and climate tab, with a backtest. Built on the synthetic climate data, so they check the method only. See `docs/MACHINE_LEARNING.md`.
- **An intent classifier** that helps IsokoBot recognise what kind of question it has been asked, when its rules find nothing. Its figures and limits are in `docs/CHATBOT_CLASSIFIER_EVALUATION.md`.

Re-create the forecast backtest (about 2 minutes): `python -m app.ml.forecast_climate`

Re-train and re-evaluate the IsokoBot classifier (about 10 seconds): `python -m app.ml.evaluate_intents`

## Folder structure
```
app/                 FastAPI application
  routers/           auth (sign-up, sign-in), prices, official statistics, admin (review, accounts),
                     district map (geo), chatbot (chat), NISR data (nisr)
  permissions.py     roles and the permission for each role (single source of truth)
  importers/         CPI file parser (handles messy NISR files)
  analytics.py       transparent calculations, including district colours (tested)
  districts.py       district report shared by the map and the chatbot
  chatbot.py         IsokoBot: grounded answers from the database only
  models.py          database schema
  seed.py            reference data, admin user, optional demo data
  static/            dashboard, sign-in page (account.html), CSS, JavaScript, Chart.js, district boundaries (data/)
tests/               pytest suite
docs/                SRS, methodology, data sources, AI disclosure, hackathon compliance
student_cards/       student eligibility documents for both team members (required by the rules)
demo/                screen recording of the interface
```

## Loading the real NISR CPI file
Sign in as admin and call `POST /api/admin/import-cpi?name=...&period=...` from the `/docs` page, uploading the CSV. Then record the file in `docs/DATA_SOURCES.md` and run `python -m app.seed --purge-demo`.

## Upgrading an existing database
Databases created before accounts had roles are upgraded automatically the first time the app starts. Columns are added, and old `contributor` accounts become `farmer_seller` accounts.

## Known limitations
- No real market price data is loaded yet. Coverage is one market in each of four districts, so most districts are grey.
- The CPI figures are national. NISR district-level CPI is not used here, so districts are coloured from market prices only.
- IsokoBot answers a fixed set of question types; it does not interpret free text beyond them.
- No rate limiting, no database migrations (Alembic) yet, and no SMS or USSD alerts.
- The CPI parser's layout detection must be checked against the real NISR file.

## Attribution
- District boundaries: geoBoundaries (CC BY 4.0). Source: www.geoboundaries.org
- Charts: Chart.js (bundled in `app/static/chart.umd.js`)

## Indicators map (v5)

The **Indicators map** tab shows the district indicator workbooks on the map. Choose an indicator, move the year slider or press **Play years**, and switch between values and the change from the year before. Clicking a district shows its chart, its change in every year, and every indicator for that year. The tab also shows the national summary and the food security score by district and year (with a CSV download).

**The indicator data is SYNTHETIC demonstration data.** Only the national agricultural input figures are recorded from real sources, and they are not re-checked here.

Upgrading an existing copy:
1. `pip install -r requirements.txt` (adds `openpyxl`).
2. `python -m app.seed --demo` (loads the four workbooks; safe to run again).
3. Restart the server.

## Version 6: welcome page, weather and climate, price map

- **Welcome page** at `/`: photo slideshow with a "Continue to dashboard" button. The main app is at `/dashboard`.
- **Weather and climate** tab: monthly rainfall and temperature for each district (2016 to 2025), compared with
  normal, with a map and the likely farming impact. SYNTHETIC demo data, labelled on every screen.
- **Market prices**: eight added products (beef, goat meat, fresh milk, bananas, avocados, cabbage, onions, wheat
  flour), four added markets, and one demonstration market in each remaining district (30 markets in total), so every district is coloured. Demo prices are synthetic. A price map by district sits under the price table.
- Existing figures are unchanged: overall district colours still use the six original staple products, and the
  original four markets keep their figures.

Upgrading an existing database: run `python -m app.seed --demo` again. It adds only what is missing.

