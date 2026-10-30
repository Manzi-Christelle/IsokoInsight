# NISR 2026 Big Data Hackathon - compliance check

Checked on 23 October 2026 against:
- **Competition brief** (2026_Hackathon_Competition.pdf): tracks, participation rules, submission, timeline, evaluation criteria, prizes.
- **Preparatory webinar** (2026_NISR_Hackathon_Webinar.pdf): submission format, video rules, data access, judging criteria, hints.

Status key: **Met** = in the repository and checked. **Partly** = started or needs data or evidence. **Not met** = still to do. **Team** = only the team can confirm this (eligibility, registration, signatures, hosting accounts).

## 1. Deadlines (urgent)

| Requirement | Date | Status | Action |
|---|---|---|---|
| Registration deadline | 20 Oct 2026, 11:59 PM | **Team, urgent: date has passed** | Confirm the team is registered on the portal. If not, contact Prosper Ayinebyona (prosper.ayinebyona@statistics.gov.rw, 0786 872 057) immediately. |
| Submission deadline | 30 Oct 2026, 11:59 PM | Team | Submit the GitHub link, the deployed app link and documentation before this time. |
| Review and evaluation | 1-5 Nov 2026 | n/a | - |
| Shortlist announced | 13 Nov 2026 | n/a | - |

## 2. Eligibility and team

| Requirement | Status | Evidence / action |
|---|---|---|
| Undergraduate or master's student, any field | Team | Confirmed by both members. |
| Student card | Team | Keep ready for upload or verification. |
| Team of 2 students, at least one Rwandan citizen | Team | The AI disclosure lists 2 members. Both are Rwandans and students as menstioned in the student_cards' README |
| Previous 1st-3rd place winners not eligible | Team | Confirm neither member won a past NISR Big Data Hackathon. |
| Final-year and female participants encouraged | n/a | Encouragement only. |
| Any programming language allowed | Met | Python (FastAPI) and JavaScript. |

## 3. Tracks and content

| Requirement | Status | Evidence / action |
|---|---|---|
| Choose a track: 1 Agriculture, 2 Financial inclusion and poverty, or 3 Open innovation | Met | Track 1 (food-price monitoring relevant to food security and markets) and Track 3 (open innovation). State the chosen track in the README and the submission form. |
| Solutions must be informed by NISR data (with or without other open or public data) | **Partly** | Uses the real NISR CPI time series (All Rwanda, Feb 2009 to Aug 2026) and calculates headline inflation from it, plus boundaries from geoBoundaries. Rainfall, prices and district indicators are still synthetic demo data, and must be replaced with real data before submission. |
| Alignment with NST2 or Vision 2050 | **Partly** | Stated in `docs/SRS.md`. NST2 priorities confirmed from a public summary (NST2 priorities: job creation, export promotion, quality of education, reduced stunting and malnutrition, enhanced public service delivery; agriculture targets). The team should confirm the wording against the official NST2 document. Vision 2050 is not yet referenced. |
| Tangible practical impact for farmers, planners or policymakers | **Partly** | The district map and IsokoBot serve planners and citizens. There is no evidence yet of real users or partners. A short user statement in the README would help. |

## 4. Submission requirements

| Requirement | Status | Evidence / action |
|---|---|---|
| Public GitHub link | Not met | Create a **public** repository and push the project. Do not push `.env`, `.venv`, `isoko.db` or `__pycache__` (already in `.gitignore`). Record the link in the README. |
| Deployed app link (publicly accessible) | Not met | Deploy the app. The Dockerfile and docker-compose.yml are included but have not yet been tested with PostgreSQL, so test them before relying on them. Hosts such as Render or Railway, or a university server, are options. Test the link in a private browser window. |
| Sample credentials if login is required | Not met | The Review tab needs an administrator. Provide a reviewer administrator login with the submission, not in the repository. Contributors can also register. |
| Documentation | Met | README, SRS, methodology, data sources, AI disclosure and this checklist. |
| Repository has at least 4 files: README, script(s), video, data file(s) with a link | **Partly** | README: Met. Scripts: Met. Video: Met (`demo/demo.webm`, 38 seconds). Data: the boundary file is included; the market and CPI data are still synthetic demo values, so real data or a link is needed. |
| README: what data is used, what it communicates, how users interact | Met | README sections "What the app shows", "How the district colours work", "How IsokoBot works", "Data sources". |
| Scripts work on any machine | Met (Linux checked) | `requirements.txt`, `Dockerfile`, `docker-compose.yml`. 37 tests pass. Windows was not tested in this session; the team should run `python -m pytest -q` on a second machine. |
| Video of the user interface and functionality, .webm or .gif | Met | `demo/demo.webm` shows the overview, market prices, comparison, district map and IsokoBot (38 seconds, under the 3-minute limit). It was recorded with a browser automation tool, not the screen-recording software NISR recommends. If the organisers require Screencastify, re-record with it. Do not use a phone camera unless the app is a mobile app. |
| Data file(s) used and a link | **Partly** | See the row above. |
| Plagiarism prohibited; declare the work is original | Team | Each member must sign the declaration. |
| AI tools allowed if disclosed; team fully responsible | Partly | `docs/AI_DISCLOSURE.md` describes the AI use. Its TODO asks each member to read and understand the code and rewrite the statement in their own words. This is required before submission. |
| By entering, IP is assigned to NISR | Team | Read and accept this term before submitting. |

## 5. Judging criteria (5 criteria, 20 points each)

| Criterion | What the brief asks for | Current evidence | Gap |
|---|---|---|---|
| 1. Problem understanding and relevance | Clear problem and alignment with NST2 or Vision 2050 | SRS problem statement and NST2 alignment statement | Confirm NST2 wording. Add Vision 2050 reference. |
| 2. Data use and methodology | Appropriate, innovative use of NISR and external data; sound methods; preprocessing quality | Two data streams kept apart; verified-only prices; documented formulas; CPI cleaning; tests for colour boundaries | Real NISR CPI and real market prices are not loaded. Headline figures need checking against the release. |
| 3. Tech innovation | Quality of tools; creativity (predictive models, satellite analysis, smart alert systems) | Interactive district choropleth from official boundaries; grounded chatbot; review flags; audit trail | Chatbot is rule-based, not an AI model. This is a deliberate choice for accuracy and can be described as such. |
| 4. Usability and design | Intuitive interface; clear data visualisation; user-friendliness | Map with legend and text labels (not colour alone); table alternative; keyboard support; mobile layout checked at 390 px; chatbot with suggestions | Test with 2-3 real users and record the feedback. |
| 5. Tangible impact | Potential for real use by government, citizens, civil society or development partners | Targeted at NISR, planners and citizens; demo shows how a district would be flagged | Name a potential user or partner. Real data is needed to show impact. |

## 6. Hints from the webinar

| Hint | Status |
|---|---|
| Use other datasets such as shapefiles for map visualisations | Met: geoBoundaries district boundaries (GeoJSON) drive the map. |
| Focus on functionality over fancy aesthetics; tell the story with the data | Met: the map, table and chatbot answer the question directly. |
| Use time wisely; do not leave work to the last minute | Team: 7 days remain. |
| NISR dataset access (microdata portal, register, request "Get Microdata") | Team: register at the NISR microdata catalogue (https://microdata.statistics.gov.rw/index.php/catalog), confirm the email, and request a public-use dataset such as the Agriculture Household Survey. Access is usually granted immediately. Record the dataset in `docs/DATA_SOURCES.md`. |
| GitHub: commit with `git add .`, `git commit`, `git push origin main` | Team: create the public repository and push. |

## 7. Security and clean-up before submission (found during this check)

| Issue | Action |
|---|---|
| The uploaded `.env` file contains a real administrator password. | **Change the password now** and never commit `.env`. The copy delivered with this check excludes `.env`. |
| `isoko.db` holds synthetic demo data. | Remove demo data with `python -m app.seed --purge-demo` before judging, or ship without the database (it is git-ignored). |
| The uploaded project included a Windows `.venv` folder (about 60 MB of Windows binaries). | Exclude it from the repository. |
| `SECRET_KEY` default is `change-me-in-production`. | Set a strong key in the hosting environment and set `APP_ENV=production` there. The app refuses to start in production with the default key. |
| The admin email and password used in the demo are defaults. | Use the sample reviewer login described in section 4, and rotate it after judging. |

## 8. Summary

Met in the code: the district map, IsokoBot, the documentation set, the 37-test suite, the demo video and the mobile layout.

Not yet met, and needed before 30 October 2026, 11:59 PM: public GitHub repository, deployed app with a sample login, real or linked data, signed declarations, and confirmed registration (the registration deadline was 20 October).
