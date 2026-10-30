"""Train and evaluate the IsokoBot intent classifier, then save the final model.

Run:  python -m app.ml.evaluate_intents

1. Train on the training templates only.
2. Score the held-out templates (phrasings the model never saw) and the challenge set (written separately).
3. Write docs/CHATBOT_CLASSIFIER_EVALUATION.md with the numbers.
4. Train the final model on all templates and save it to app/ml/artifacts/intent_model.joblib.
"""
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, classification_report, f1_score

from .intent_classifier import ARTIFACT, HIGH, MEDIUM, fit
from .intent_data import CLARIFY, CANONICAL, OUT_OF_SCOPE, build, challenge

REPORT = Path(__file__).resolve().parents[2] / "docs" / "CHATBOT_CLASSIFIER_EVALUATION.md"


def _predict(model, texts):
    probs = model.predict_proba(texts)
    best = probs.argmax(axis=1)
    return [str(model.classes_[i]) for i in best], probs.max(axis=1)


def _oos_routing(preds, confs, truth):
    """Out-of-scope questions that would wrongly trigger an answer or a Yes/No offer."""
    oos = [i for i, t in enumerate(truth) if t == OUT_OF_SCOPE]
    if not oos:
        return 0.0, 0.0
    acted = [i for i in oos if preds[i] != OUT_OF_SCOPE and confs[i] >= HIGH]
    offered = [i for i in oos if preds[i] != OUT_OF_SCOPE and confs[i] >= MEDIUM]
    return len(acted) / len(oos), len(offered) / len(oos)


def _acting(preds, confs, truth):
    """Share of questions where the classifier would act (probability {HIGH:.2f} or more), split into right and wrong."""
    acts = [(p, t) for p, c, t in zip(preds, confs, truth) if c >= HIGH]
    right = sum(1 for p, t in acts if p == t)
    return len(acts) / len(truth), right / len(truth), (len(acts) - right) / len(truth)


def _table(report: dict) -> list[str]:
    lines = ["| Intent | Precision | Recall | F1 | Examples |", "|---|---|---|---|---|"]
    for name, row in report.items():
        if name in ("accuracy", "macro avg", "weighted avg"):
            continue
        lines.append(f"| {name} | {row['precision']:.2f} | {row['recall']:.2f} | {row['f1-score']:.2f} | {int(row['support'])} |")
    return lines


def main() -> None:
    train_x, train_y = build("train")
    hold_x, hold_y = build("holdout")
    chal_x, chal_y = challenge()

    model = fit(train_x, train_y)
    hold_pred, hold_conf = _predict(model, hold_x)
    chal_pred, chal_conf = _predict(model, chal_x)

    hold_acc = accuracy_score(hold_y, hold_pred)
    hold_f1 = f1_score(hold_y, hold_pred, average="macro")
    chal_acc = accuracy_score(chal_y, chal_pred)
    chal_f1 = f1_score(chal_y, chal_pred, average="macro")
    hold_rep = classification_report(hold_y, hold_pred, output_dict=True, zero_division=0)
    chal_rep = classification_report(chal_y, chal_pred, output_dict=True, zero_division=0)
    oos_acted_h, oos_offered_h = _oos_routing(hold_pred, hold_conf, hold_y)
    oos_acted_c, oos_offered_c = _oos_routing(chal_pred, chal_conf, chal_y)
    act_h = _acting(hold_pred, hold_conf, hold_y)
    act_c = _acting(chal_pred, chal_conf, chal_y)

    misses = [(t, y, p, round(c, 2)) for t, y, p, c in zip(chal_x, chal_y, chal_pred, chal_conf) if y != p]
    confusions = Counter((y, p) for y, p in zip(hold_y + chal_y, hold_pred + chal_pred) if y != p).most_common(8)

    final = fit(*build("all"))
    import joblib
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final, ARTIFACT)

    lines = [
        "# IsokoBot intent classifier: evaluation",
        "",
        f"Generated {date.today().isoformat()} by `python -m app.ml.evaluate_intents`.",
        "",
        "## What was measured",
        "",
        f"- Training examples: {len(train_x)}, from the training templates only.",
        f"- Held-out examples: {len(hold_x)}, from templates the model never saw (one in every four).",
        f"- Challenge questions: {len(chal_x)}, written separately in different words. Never used for training.",
        f"- Thresholds: act at a probability of {HIGH:.2f} or more, offer a Yes/No suggestion between {MEDIUM:.2f} and {HIGH:.2f}.",
        "",
        "**Development history.** The first run of this evaluation scored 63.6 per cent on the held-out templates, "
        "with district status almost never recognised. The model was then changed: district, product, "
        "indicator and year names are masked before classification, and more templates were added for the "
        "weakest intents. The held-out templates were used to judge those changes, so the challenge set is the "
        "cleaner measure. The challenge set was not used for any decision.",
        "",
        "**Limitation.** The authors wrote every example. This is not an independent external test. "
        "The challenge set is a stricter check than the held-out templates, but it still does not replace "
        "questions written by people outside the team.",
        "",
        "## Results",
        "",
        "| Measure | Held-out templates | Challenge questions |",
        "|---|---|---|",
        f"| Accuracy | {hold_acc:.1%} | {chal_acc:.1%} |",
        f"| Macro F1 | {hold_f1:.2f} | {chal_f1:.2f} |",
        f"| Out-of-scope questions that would trigger an answer (probability {HIGH:.2f} or more) | {oos_acted_h:.0%} | {oos_acted_c:.0%} |",
        f"| Out-of-scope questions that would trigger a Yes/No offer (probability {MEDIUM:.2f} or more) | {oos_offered_h:.0%} | {oos_offered_c:.0%} |",
        f"| Questions answered correctly without a guess (probability {HIGH:.2f} or more) | {act_h[1]:.0%} | {act_c[1]:.0%} |",
        f"| Questions answered wrongly (probability {HIGH:.2f} or more) | {act_h[2]:.0%} | {act_c[2]:.0%} |",
        f"| Questions left to the \"can't respond\" reply or the wording suggester (probability below {HIGH:.2f}) | {1 - act_h[0]:.0%} | {1 - act_c[0]:.0%} |",
        "",
        f"The out-of-scope rows and the wrong-answer row are the most important. A question IsokoBot cannot answer, "
        "or one it answers wrongly, is worse than no answer, so the thresholds were set to keep those rows low.",
        "",
        "## Held-out templates, by intent",
        "",
        *_table(hold_rep),
        "",
        "## Challenge questions, by intent",
        "",
        *_table(chal_rep),
        "",
        "## Challenge questions the classifier got wrong",
        "",
        "| Question | Correct intent | Predicted | Probability |",
        "|---|---|---|---|",
        *[f"| {t} | {y} | {p} | {c} |" for t, y, p, c in misses],
        "" if misses else "None.",
        "",
        "## Most common confusions (held-out and challenge together)",
        "",
        "| Correct intent | Predicted as | Count |",
        "|---|---|---|",
        *[f"| {y} | {p} | {n} |" for (y, p), n in confusions],
        "",
        "## What IsokoBot does with each score",
        "",
        f"- Probability {HIGH:.2f} or more, intent with no entity ({', '.join(CANONICAL)}): answers the matching question and says which question it answered.",
        f"- Probability {HIGH:.2f} or more, intent that needs a detail ({', '.join(CLARIFY)}): asks for the missing detail. It does not guess.",
        f"- Probability {MEDIUM:.2f} to {HIGH:.2f}, intent with no entity: offers Yes/No, using the matching question.",
        f"- Below {MEDIUM:.2f}, or out of scope: replies \"can't respond to this!\".",
        "- The wording suggester (Viterbi) runs first, as before. The classifier is only used when the suggester has nothing.",
        "",
        "The saved model is trained on all templates, including the held-out ones, so the app has seen every template.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Held-out accuracy {hold_acc:.1%}, challenge accuracy {chal_acc:.1%}")
    print(f"Out-of-scope acted on (challenge): {oos_acted_c:.0%}; offered (challenge): {oos_offered_c:.0%}")
    print(f"Report written to {REPORT}")
    print(f"Model saved to {ARTIFACT}")


if __name__ == "__main__":
    main()
