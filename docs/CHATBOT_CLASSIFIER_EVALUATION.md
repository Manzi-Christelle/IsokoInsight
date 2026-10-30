# IsokoBot intent classifier: evaluation

Generated 2026-10-30 by `python -m app.ml.evaluate_intents`.

## What was measured

- Training examples: 984, from the training templates only.
- Held-out examples: 320, from templates the model never saw (one in every four).
- Challenge questions: 34, written separately in different words. Never used for training.
- Thresholds: act at a probability of 0.70 or more, offer a Yes/No suggestion between 0.50 and 0.70.

**Development history.** The first run of this evaluation scored 63.6 per cent on the held-out templates, with district status almost never recognised. The model was then changed: district, product, indicator and year names are masked before classification, and more templates were added for the weakest intents. The held-out templates were used to judge those changes, so the challenge set is the cleaner measure. The challenge set was not used for any decision.

**Limitation.** We wrote every example. This is not an independent external test. The challenge set is a stricter check than the held-out templates, but it still does not replace questions written by people outside the team. Also the bot doesn't understand most kinyarwanda words except some words like ibishyimbo, umuceri, ibirayi and ibigori.

## Results

| Measure | Held-out templates | Challenge questions |
|---|---|---|
| Accuracy | 75.0% | 76.5% |
| Macro F1 | 0.72 | 0.65 |
| Out-of-scope questions that would trigger an answer (probability 0.70 or more) | 0% | 0% |
| Out-of-scope questions that would trigger a Yes/No offer (probability 0.50 or more) | 4% | 0% |
| Questions answered correctly without a guess (probability 0.70 or more) | 20% | 41% |
| Questions answered wrongly (probability 0.70 or more) | 1% | 0% |
| Questions left to the "can't respond" reply or the wording suggester (probability below 0.70) | 79% | 59% |

The out-of-scope rows and the wrong-answer row are the most important. A question IsokoBot cannot answer, or one it answers wrongly, is worse than no answer, so the thresholds were set to keep those rows low.

## Held-out templates, by intent

| Intent | Precision | Recall | F1 | Examples |
|---|---|---|---|---|
| ask_product | 0.80 | 0.33 | 0.47 | 12 |
| categories | 0.73 | 0.67 | 0.70 | 12 |
| climate | 0.94 | 0.50 | 0.65 | 32 |
| colour_meaning | 1.00 | 0.67 | 0.80 | 12 |
| contribute | 0.50 | 0.92 | 0.65 | 12 |
| critical_zone | 0.80 | 0.75 | 0.77 | 16 |
| data_status | 0.63 | 1.00 | 0.77 | 12 |
| district_status | 0.60 | 0.97 | 0.74 | 32 |
| help | 0.80 | 0.25 | 0.38 | 16 |
| indicator | 1.00 | 0.96 | 0.98 | 24 |
| inflation | 1.00 | 0.50 | 0.67 | 16 |
| methodology | 0.69 | 0.92 | 0.79 | 12 |
| out_of_scope | 0.69 | 0.77 | 0.73 | 52 |
| price_period | 1.00 | 1.00 | 1.00 | 24 |
| product_price | 0.82 | 0.96 | 0.88 | 24 |
| sources | 0.56 | 0.42 | 0.48 | 12 |

## Challenge questions, by intent

| Intent | Precision | Recall | F1 | Examples |
|---|---|---|---|---|
| ask_product | 1.00 | 1.00 | 1.00 | 1 |
| categories | 1.00 | 1.00 | 1.00 | 1 |
| climate | 0.67 | 1.00 | 0.80 | 2 |
| colour_meaning | 0.00 | 0.00 | 0.00 | 1 |
| contribute | 0.33 | 1.00 | 0.50 | 1 |
| critical_zone | 1.00 | 0.50 | 0.67 | 2 |
| data_status | 1.00 | 1.00 | 1.00 | 1 |
| district_status | 1.00 | 1.00 | 1.00 | 2 |
| help | 0.50 | 1.00 | 0.67 | 1 |
| indicator | 1.00 | 0.50 | 0.67 | 2 |
| inflation | 0.00 | 0.00 | 0.00 | 2 |
| methodology | 0.50 | 1.00 | 0.67 | 1 |
| out_of_scope | 0.79 | 0.92 | 0.85 | 12 |
| price_period | 1.00 | 1.00 | 1.00 | 2 |
| product_price | 1.00 | 0.50 | 0.67 | 2 |
| sources | 0.00 | 0.00 | 0.00 | 1 |

## Challenge questions the classifier got wrong

| Question | Correct intent | Predicted | Probability |
|---|---|---|---|
| what regions are flagged red | critical_zone | help | 0.35 |
| avocado price right now | product_price | contribute | 0.5 |
| grain stock in Rusizi in 2015 | indicator | climate | 0.61 |
| what is the cost of living growth rate | inflation | out_of_scope | 0.44 |
| how much has the general index risen | inflation | methodology | 0.45 |
| what do the shades on the map signify | colour_meaning | out_of_scope | 0.62 |
| who gives you the statistics | sources | out_of_scope | 0.38 |
| how do I reset my phone | out_of_scope | contribute | 0.4 |


## Most common confusions (held-out and challenge together)

| Correct intent | Predicted as | Count |
|---|---|---|
| climate | district_status | 12 |
| help | out_of_scope | 8 |
| out_of_scope | contribute | 8 |
| sources | data_status | 7 |
| inflation | out_of_scope | 5 |
| inflation | methodology | 5 |
| colour_meaning | out_of_scope | 5 |
| critical_zone | district_status | 4 |

## What IsokoBot does with each score

- Probability 0.70 or more, intent with no entity (critical_zone, inflation, categories, colour_meaning, methodology, contribute, sources, data_status, ask_product, help): answers the matching question and says which question it answered.
- Probability 0.70 or more, intent that needs a detail (district_status, product_price, price_period, indicator, climate): asks for the missing detail. It does not guess.
- Probability 0.50 to 0.70, intent with no entity: offers Yes/No, using the matching question.
- Below 0.50, or out of scope: replies "can't respond to this!".
- The wording suggester (Viterbi) runs first, as before. The classifier is only used when the suggester has nothing.

The saved model is trained on all templates, including the held-out ones, so the app has seen every template.
