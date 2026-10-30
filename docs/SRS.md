# Software Requirements Specification (summary)

Problem: official CPI statistics do not show current item-level prices by market, and districts have no simple view of where food prices are high. Comparisons are error-prone when units, dates or sources differ.

Alignment: National Strategy for Transformation 2 (NST2) priority of reducing stunting and malnutrition depends on affordable food; NST2 also sets agricultural productivity and market targets. The app supports monitoring of food prices by district and market for planners and citizens. (The team should confirm the exact NST2 wording against the official document before submission.)

| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-01 | Public dashboard of food-price information | Must | Done |
| FR-02 | Filter prices by product, market, date | Must | Done (unit filter via API) |
| FR-03 | Compare same product across markets, same unit only | Must | Done |
| FR-04 | Historical price and CPI charts | Must | Done |
| FR-05 | Contributors submit observations | Must | Done |
| FR-06 | Admin approve/reject/correct with audit trail | Must | Done |
| FR-07 | Each price shows source, date, unit, status | Must | Done |
| FR-08 | CPI import with source attribution | Must | Done (needs real file) |
| FR-09 | Flag unusual changes for review | Should | Done |
| FR-10 | CSV download | Should | Done |
| FR-11 | Price alerts to users, SMS/USSD | Later | Not started |
| FR-12 | District map: every district coloured red (critical), yellow (medium) or green (good), grey where data is insufficient | Must | Done (market-price basis) |
| FR-13 | Chatbot answers questions from verified data and official figures, citing sources, never inventing numbers | Must | Done (rule-based) |
| FR-14 | Synthetic data labelled wherever it appears | Must | Done |
| FR-15 | Sign-in and sign-up page; choice of role at sign-up | Must | Done |
| FR-16 | Five roles (customer, farmer/seller, enumerator, NISR statistician, administrator) with permissions enforced on the server | Must | Done (see docs/ACCESS_CONTROL.md) |
| FR-17 | Enumerator and NISR accounts approved by an administrator before sign-in | Must | Done |
| FR-18 | NISR full dataset export and statistics generation | Must | Done |
| FR-19 | Administrator manages accounts (approve, disable, change role) | Must | Done |
| NFR-01 | Works on any machine: pinned requirements, Dockerfile, Docker Compose, tests | Must | Done (tested on Linux, Python 3.13) |
| NFR-02 | Mobile responsive, no horizontal scroll at phone width | Should | Done (checked at 390px) |
| NFR-03 | Colour is not the only signal: legend text, table with status words | Should | Done |

Non-functional: hashed passwords (PBKDF2), validated inputs, documented API (/docs), tests (pytest).
Known gaps: no rate limiting, no database migrations (Alembic), no real market data yet, real NISR CPI not yet imported, deployment not yet done.
