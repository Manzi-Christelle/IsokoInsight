# Machine-learning additions (version 12)

Two additions use machine learning. Both are estimates, both are labelled, and neither changes official statistics, verified prices or the stored synthetic data.

1. **Rainfall and temperature forecasts** for each district, with a backtest. Built on the **SYNTHETIC** climate data. It checks the method only.
2. **An intent classifier for IsokoBot**. It helps IsokoBot recognise what kind of question it has been asked. Its answers still come from the rules and the database.

## 1. Rainfall and temperature forecasts

**Where it appears.** Weather and climate tab, below the monthly chart: "Forecast for the next months". Choose a district, rainfall or temperature, and 1 to 6 months ahead.

**Data.** The synthetic monthly values for 30 districts, 2016 to 2025 (120 months each). Source: DEMO - synthetic rainfall and temperature. The results do not describe real weather in Rwanda.

**Methods.**
- *Climatology:* the average of the same calendar month in earlier years. A baseline.
- *Seasonal naive:* the value of the same month last year. A baseline.
- *Holt-Winters smoothing:* yearly seasonality with a damped trend, fitted with statsmodels. Rainfall is smoothed on a log(1 + mm) scale, so forecasts stay positive.

**Backtest.** Each method is fitted only to the data before a forecast origin and asked for the next 6 months. The forecast is compared with the synthetic value that followed. Origins are every 3 months, from the fourth year onward: 810 origins for each measure (30 districts, 27 origins). The results are saved in `app/ml/artifacts/climate_backtest.json`.

**Results (mean absolute error; smoothing model against climatology).**

| Horizon | Rainfall: smoothing (mm) | Rainfall: climatology (mm) | Rainfall verdict | Temperature: smoothing (°C) | Temperature: climatology (°C) | Temperature verdict |
|---|---|---|---|---|---|---|
| 1 month | 10.22 | 10.79 | Beats | 0.37 | 0.42 | Beats |
| 2 months | 10.05 | 10.74 | Beats | 0.36 | 0.41 | Beats |
| 3 months | 10.44 | 10.50 | Beats (marginally) | 0.36 | 0.41 | Beats |
| 4 months | 11.87 | 10.92 | Does not beat | 0.43 | 0.42 | Does not beat |
| 5 months | 11.33 | 11.02 | Does not beat | 0.42 | 0.41 | Does not beat |
| 6 months | 10.71 | 10.25 | Does not beat | 0.42 | 0.41 | Does not beat |

Seasonal naive was clearly worse than both at every horizon (about 14 mm for rainfall and 0.5 °C for temperature).

**Intervals.** The 80 per cent range is the forecast plus or minus 1.28 times the backtest RMSE for that horizon. Measured coverage was 80 to 87 per cent for rainfall and 82 to 84 per cent for temperature, close to the 80 per cent target. The coverage is measured on the same backtest that sets the width, so it is optimistic.

**What this means.** On the synthetic data, the smoothing model helps for the first three months and no longer beats the simple climatology after that. On real data the picture could be different, and it would need its own backtest. The panel shows the verdict for each horizon, so a reader can see where the method is useful.

**Endpoint.** `GET /api/forecast/climate?district=Musanze&variable=rain&horizon=3`

**Re-run the backtest** (about 2 minutes):

```bash
python -m app.ml.forecast_climate
```

## 2. IsokoBot intent classifier

**Where it appears.** Inside IsokoBot. It runs only when no rule matches and the wording suggester (Viterbi) has no suggestion. Existing answers are unchanged.

**What it decides.** The kind of answer a question needs: one of 15 intents (listed in `docs/CHATBOT_CLASSIFIER_EVALUATION.md`), or "out of scope".

**How it decides.**
- District, product, year, period and indicator names are masked, so the model learns the wording and not the names. The rules still find the actual names.
- Character n-gram TF-IDF (2 to 5 characters) copes with spelling mistakes and mixed spellings such as fertiliser and fertilizer.
- Logistic regression, with its probabilities calibrated by a sigmoid fit.

**What IsokoBot does with each score.**
- 0.70 or more, a question that needs no detail: answers the matching question and says which one it answered.
- 0.70 or more, a question that needs a detail (district, product, period, indicator or year): asks for the missing detail. It does not guess.
- 0.50 to 0.70, a question that needs no detail: offers Yes and No.
- Below 0.50, or out of scope: "can't respond to this!".

**Evaluation.** Full figures are in `docs/CHATBOT_CLASSIFIER_EVALUATION.md`.

| Measure | Held-out templates | Challenge questions |
|---|---|---|
| Accuracy | 75.0% | 76.5% |
| Questions answered correctly without a guess (0.70 or more) | 20% | 41% |
| Questions answered wrongly (0.70 or more) | 1% | 0% |
| Out-of-scope questions that would trigger an answer | 0% | 0% |

**How the threshold was chosen.** The 0.70 threshold was chosen on the held-out templates, where it gives 1 per cent wrong answers. On the challenge set it gives none. A threshold of 0.50 would answer more questions, but it gives 7 per cent wrong answers on the held-out templates. The threshold was set to keep wrong answers low.

**Important limitations.**
- The authors wrote every example. This is not an independent external test. People outside the team should write a further set of questions before the classifier's accuracy is reported as established.
- The classifier is conservative. It acts on 20 per cent of held-out questions and 41 per cent of challenge questions. The rest get the fixed reply or the existing suggestions.
- Some in-scope questions are refused, for example "show the grain stock". Refusing is safer than answering wrongly, but it is still a miss.
- Held-out results were used to choose the threshold and to judge the masking change. The challenge set was not used for any decision, so it is the cleaner measure.

**Re-train and re-evaluate** (about 10 seconds). This also saves the final model to `app/ml/artifacts/intent_model.joblib`:

```bash
python -m app.ml.evaluate_intents
```

## Bugs fixed while testing

Writing the classifier tests exposed two rules that wrongly treated the word "good" as a district colour. "Recommend a good book" was answered with the district colour summary, and "what is a good price for maize" was answered with the colour explanation. The word "good" has been removed from both rules. The word "green" and the colour words remain, so colour questions still work.

## Packages added

`numpy`, `scikit-learn` and `statsmodels`, listed in `requirements.txt`. The Docker image grows by a few tens of megabytes.

## Files

| File | Purpose |
|---|---|
| `app/ml/__init__.py` | Describes the package and its rule: every output is an estimate and never changes official data. |
| `app/ml/forecast_climate.py` | The forecast methods, the backtest and the forecast for one district. |
| `app/ml/artifacts/climate_backtest.json` | The saved backtest results. |
| `app/routers/forecast.py` | The forecast endpoint. |
| `app/static/forecast.js` | The forecast panel on the Weather and climate tab. |
| `app/ml/intent_data.py` | The training templates, the challenge questions, the entity masking and the canonical questions. |
| `app/ml/intent_classifier.py` | The classifier pipeline, the thresholds and the prediction function. |
| `app/ml/evaluate_intents.py` | Trains, evaluates and saves the classifier, and writes the evaluation report. |
| `app/ml/artifacts/intent_model.joblib` | The saved classifier. |
| `docs/CHATBOT_CLASSIFIER_EVALUATION.md` | The classifier evaluation report, generated by the script. |
| `tests/test_forecast_climate.py` | Tests for the methods, the endpoint, the read-only rule and the backtest. |
| `tests/test_intent_classifier.py` | Tests for the classifier, the masking and the chatbot routing. |
