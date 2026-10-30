# AI use disclosure (NISR 2026 Big Data Hackathon)

Team name: The backbone
Team members: MUCYO MANZI Marie Christelle (team leader) and MUGISHA Kevin.

## Tools used

- Claude (Anthropic), used as a coding and writing assistant.
- ChatGPT (OpenAI), used for early planning and drafting.
- Grok AI, used for data checking and code refinement.

## What the AI tools were used for

- Project planning and drafting the requirements document.
- Generating starter code for the web app (FastAPI backend, browser pages) and reviewing it.
- Writing automated tests, and writing the project documentation (README, methodology, data sources).
- Later features: the welcome page, the Weather and climate tab, the market price map, the district indicator
  maps, and the IsokoBot chatbot rules. This included finding a public Rwanda district boundary file,
  simplifying it for the web, writing the colour rules, and checking the pages in a browser.
- Generating the synthetic demonstration data (a script that creates prices, climate values and district
  indicator workbooks). This data is labelled as synthetic in the app and in the files, and it is not
  NISR data.

## What the team did itself

- Chose the problem (food prices and farming conditions in Rwanda's districts) and the Track 1 focus.
- Decided which official and open data to use, and recorded each source in `docs/DATA_SOURCES.md`.
- Tested the app, checked the outputs against the source data, and corrected errors found in testing.
- Prepared the submission (repository, deployment, demo video and this statement).

## How the team checked the AI output

- Every rule that decides a colour, band or impact class is covered by an automated test.
- Every number shown in the app is read from the database, and synthetic values carry a visible label.
- Official NISR figures are checked against the NISR release before use, not typed in from memory.
- For a user to contribute any data, they have to sign in and wait for admin approval for the contributed data.

## Responsibility

The team is fully responsible for the submitted work. The AI tools are assistants only. Data sources are listed in the in-app Sources page and in `docs/DATA_SOURCES.md`. Synthetic demonstration data is not removed.

## Declaration by each team member

I Mucyo Manzi Marie Christelle and Mugisha Kevin approve that the statements above are accurate, that we have read, run and can explain the submitted codes, that the work is our own original work. The work has not been submitted to any other competition, and we accept the intellectual property terms in the competition rules.

Member 1: MUCYO MANZI Marie Christelle (team leader)

Signature: Manzi_Christelle    Date: 29t October 2026

Member 2: MUGISHA Kevin

Signature: Mugisha_Kevin    Date: 29th October 2026
