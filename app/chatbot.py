"""IsokoBot: a grounded assistant for the food-price dashboard.

Design rules:
  * Every number comes from the database or the stored official figures. Nothing is invented.
  * Only VERIFIED prices are used. Pending or rejected submissions are never quoted.
  * Synthetic demo data is always labelled as demo.
  * Each answer lists the sources it used.
  * If the question is not understood, it says so and lists what it can answer.
"""
import re

from sqlalchemy.orm import Session, joinedload

from . import analytics
from .config import settings
from .chatbot_climate import (SOURCE_FORECAST, climate_answer, followup_answer, forecast_answer, forecast_explanation,
                              wants_climate, wants_followup, wants_forecast, wants_forecast_explanation)
from .chatbot_indicators import indicator_answer, match_indicators, requested_season, requested_year
from .chatbot_prices import parse_period, price_period_answer, wants_explanation
from .chatbot_suggest import suggest_question
from .ml.intent_classifier import HIGH, MEDIUM, is_out_of_scope, predict_intent
from .ml.intent_data import CANONICAL, CLARIFY
from .districts import STATUS_LABELS, district_report, load_district_names
from .models import DataSource, Market, OfficialIndicator, OfficialSeries, OfficialValue, PriceObservation, Product

# Product names and common ways people refer to them (English and Kinyarwanda).
PRODUCT_ALIASES = {
    "Irish potatoes": ["irish potato", "irish potatoes", "potato", "potatoes", "ibirayi"],
    "Maize flour": ["maize flour", "maize", "corn", "ibigori"],
    "Dry beans": ["dry beans", "beans", "bean", "ibishyimbo"],
    "Tomatoes": ["tomato", "tomatoes", "inyanya"],
    "Rice": ["rice", "umuceri"],
    "Cooking oil": ["cooking oil", "oil", "amavuta"],
}

HELP = ("I can answer questions about:\n"
        "- District status on the map (critical, medium, good)\n"
        "- Verified market prices for a product, optionally in one district\n"
        "- District indicators for a year, such as grain held in reserve in Musanze in 2010\n"
        "- NISR headline inflation and the fastest-rising CPI categories\n"
        "- Where the data comes from, and how the numbers are calculated\n"
        "- How to submit a price\n\n"
        "Try: \"Which districts are in the critical zone?\" or \"Price of maize flour in Huye\".")

SUGGESTIONS = ["Which districts are critical?", "Price of maize flour", "Grain held in reserve in Musanze",
               "What is headline inflation?", "Which categories are rising fastest?", "How are colours calculated?",
               "What data is used?"]


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text) is not None


def _find_terms(text: str, terms) -> list[str]:
    return [t for t in terms if re.search(r"\b" + re.escape(t.lower()) + r"\b", text)]


def _demo_note(flag: bool) -> str:
    return "\nDEMO DATA: these values are synthetic examples, not real Rwandan figures." if flag else ""


def _vs_median(pct: float) -> str:
    return f"{abs(pct):.1f}% {'above' if pct > 0 else 'below' if pct < 0 else 'at'} the national median"


def _verified_obs(db: Session, product_id: int | None = None):
    q = (db.query(PriceObservation)
         .options(joinedload(PriceObservation.product), joinedload(PriceObservation.market),
                  joinedload(PriceObservation.source))
         .filter(PriceObservation.status == "verified"))
    if product_id:
        q = q.filter(PriceObservation.product_id == product_id)
    return q.all()


def _product_reply(db: Session, product: Product, district: str | None):
    groups = analytics.compare_markets(_verified_obs(db, product.id)).get(product.standard_unit)
    if not groups:
        return (f"There are no verified prices for {product.name} yet. Prices appear here only after an "
                "administrator has checked them.", ["Market prices"])
    rows = groups["rows"]
    if district:
        rows = [r for r in rows if r["district"].lower() == district.lower()]
        if not rows:
            return (f"There is no verified {product.name} price for {district} yet.", ["Market prices"])
    lines = [f"{product.name}, price per {product.standard_unit}, latest verified prices:"]
    for r in rows:
        extra = "" if r is rows[0] and len(rows) == 1 else (
            f" (+{r['diff_pct_vs_cheapest']}% vs cheapest)" if r["diff_pct_vs_cheapest"] else " (cheapest)")
        lines.append(f"- {r['market']} ({r['district']}): {r['price_rwf']:,} RWF on {r['observed_on']}{extra}")
    if not district:
        lines.append(f"Cheapest market: {groups['cheapest_market']}.")
    demo = any(r["is_synthetic"] for r in rows)
    return "\n".join(lines) + _demo_note(demo), ["Verified market prices"]


def _district_reply(report: dict, name: str):
    d = next(x for x in report["districts"] if x["name"] == name)
    head = f"{name}: {d['status_label']}."
    if d["status"] in ("no_data", "limited_data"):
        body = (" The app does not have enough verified prices here to colour this district reliably."
                if d["status"] == "no_data" else
                f" Only {d['products_used']} verified product is available, so no colour is given.")
        return head + body + _demo_note(d["contains_synthetic"]), ["District status map"]
    lines = [head + f" On average, prices are {_vs_median(d['index_pct'])} across "
             f"{d['products_used']} products, using {', '.join(d['markets'])}."]
    for p in d["details"]:
        lines.append(f"- {p['product']}: {p['price_rwf']:,} RWF vs national median {p['national_median_rwf']:,} "
                     f"({p['deviation_pct']:+.1f}%)")
    t = report["thresholds"]
    lines.append(f"Bands: green up to {t['yellow_above_pct']:g}% above the median, yellow up to "
                 f"{t['red_above_pct']:g}%, red above that.")
    return "\n".join(lines) + _demo_note(d["contains_synthetic"]), ["District status map", "Verified market prices"]


def _status_summary(report: dict):
    groups = {k: [] for k in STATUS_LABELS}
    for d in report["districts"]:
        groups[d["status"]].append(d["name"])
    lines = ["District colours across Rwanda (30 districts):",
             f"- Critical zone (red): {', '.join(groups['critical']) or 'none'}",
             f"- Medium (yellow): {', '.join(groups['medium']) or 'none'}",
             f"- Good (green): {', '.join(groups['good']) or 'none'}",
             f"- No verified data or limited data (grey): {len(groups['no_data']) + len(groups['limited_data'])} districts"]
    return "\n".join(lines) + _demo_note(report["contains_synthetic"]), ["District status map"]


def _inflation_reply(db: Session):
    rows = (db.query(OfficialIndicator).filter(OfficialIndicator.name.like("Headline%"))
            .order_by(OfficialIndicator.period.desc()).all())
    if not rows:
        return "No NISR headline inflation figure is loaded yet.", []
    latest = rows[0]
    prev = next((r for r in rows[1:] if r.name == latest.name), None)
    text = (f"NISR headline inflation (year-on-year) was {latest.value:.1f}% for "
            f"{latest.period.strftime('%B %Y')}")
    if prev:
        text += f", compared with {prev.value:.1f}% for {prev.period.strftime('%B %Y')}"
    text += (f". Source: {latest.source.name}. Calculated as the year-on-year change in the NISR "
             "general CPI index.")
    return text, [latest.source.name]


def _top_categories(db: Session):
    ranked = []
    for s in db.query(OfficialSeries).all():
        pts = [(v.period, v.index_value) for v in
               db.query(OfficialValue).filter_by(series_id=s.id).order_by(OfficialValue.period)]
        data = analytics.add_changes(pts)
        if data and data[-1]["yoy_pct"] is not None:
            ranked.append((data[-1]["yoy_pct"], s.name, data[-1]["period"], s.source.name,
                           s.source.is_synthetic))
    if not ranked:
        return "No CPI category data is loaded yet.", []
    ranked.sort(reverse=True)
    lines = ["CPI categories with the largest year-on-year rises (latest month):"]
    for pct, name, period, _, _ in ranked[:5]:
        lines.append(f"- {name}: {pct:+.1f}% ({period[:7]})")
    demo = any(r[4] for r in ranked[:5])
    lines.append("These are national indices, not prices of single products.")
    return "\n".join(lines) + _demo_note(demo), sorted({r[3] for r in ranked[:5]})


def _sources_reply(db: Session):
    srcs = db.query(DataSource).order_by(DataSource.id).all()
    lines = ["Data sources recorded in the app:"]
    for s in srcs:
        tag = " (SYNTHETIC DEMO)" if s.is_synthetic else ""
        lines.append(f"- {s.name}{tag}: {s.publisher}")
    lines.append("Full details, download dates and processing steps are on the Sources tab.")
    return "\n".join(lines), [s.name for s in srcs]


METHOD_TEXT = (
    "How the numbers are calculated:\n"
    "- Change over time = (new price - earlier price) / earlier price x 100.\n"
    "- Market comparison = (market price - cheapest price) / cheapest price x 100, using the latest "
    "verified price per market and the same unit only.\n"
    "- District colour = average % difference from the national median across products, using "
    f"verified prices only. Green up to {settings.district_yellow_pct:g}%, yellow up to "
    f"{settings.district_red_pct:g}%, red above that.\n"
    f"- Review flags appear for CPI moves of {settings.cpi_mom_threshold_pct:g}% or more in a month, "
    f"or for submitted prices {settings.price_change_threshold_pct:g}% away from the last verified price. "
    "A flag asks for a check; it does not prove an error or a shortage.")

CONTRIBUTE_TEXT = (
    "To contribute a price:\n"
    "1. Sign in on the Account page (or create an account as a farmer or seller).\n"
    "2. Enter the product, market, price in RWF per standard unit, date observed and how it was collected.\n"
    "3. Submit. It stays pending until an administrator verifies it, and only then appears publicly.\n"
    "You can see the status of your submissions on the Contribute tab.")


KIGALI_DISTRICTS = ("Gasabo", "Kicukiro", "Nyarugenge")


def colour_meaning() -> str:
    return (f"The district colours compare each district's verified prices with the national median:\n"
            f"- Critical zone (red): more than {settings.district_red_pct:g}% above the median.\n"
            f"- Medium (yellow): {settings.district_yellow_pct:g}% to {settings.district_red_pct:g}% above.\n"
            f"- Good (green): up to {settings.district_yellow_pct:g}% above the median, or below it.\n"
            "- Grey: no verified data, or fewer than 2 products.\n"
            "A colour asks for attention. It does not prove a shortage.")


def direct_critical_answer(name: str, d: dict) -> str:
    if d["status"] == "critical":
        return f"Yes. {name} is in the critical zone (red)."
    return f"No. {name} is not in the critical zone. It is {d['status_label'].lower()}."


def _reply(reply: str, sources: list[str], intent: str) -> dict:
    return {"reply": reply, "intent": intent, "sources": sources, "suggestions": SUGGESTIONS[:4], "choices": []}


def _classifier_reply(db: Session, raw: str) -> dict | None:
    """The intent classifier's choice. Used only when the rules and the wording suggester found nothing.

    Above HIGH: answer the matching question (no-entity intents) or ask for the missing detail (intents that
    need one). Between MEDIUM and HIGH: offer Yes/No for a no-entity intent. Otherwise: no reply.
    """
    intent, confidence = predict_intent(raw)
    if is_out_of_scope(intent) or confidence < MEDIUM:
        return None
    if intent in CLARIFY:
        return _reply(CLARIFY[intent], [], f"classifier:{intent}") if confidence >= HIGH else None
    canonical = CANONICAL[intent]
    if confidence >= HIGH:
        inner = answer(db, canonical, _classified=True)
        inner["reply"] = f'I think you are asking: "{canonical}".\n\n' + inner["reply"]
        inner["intent"] = f"classifier:{intent}"
        return inner
    choices = [{"label": "Yes", "ask": canonical}, {"label": "No", "ask": None}]
    return {**_reply(f'Did you mean "{canonical}"?', [], "suggestion"), "choices": choices}


def answer(db: Session, message: str, _classified: bool = False, context: dict | None = None) -> dict:
    raw = (message or "").strip()
    text = raw.lower()
    report = None

    def done(reply, sources, intent):
        return {"reply": reply, "intent": intent, "sources": sources, "suggestions": SUGGESTIONS[:4], "choices": []}

    districts = _find_terms(text, load_district_names())
    if _has(r"\bkigali\b", text):  # Kigali is the city; the data is held by its three districts
        districts = sorted(set(districts) | set(KIGALI_DISTRICTS))
    markets = [m for m in db.query(Market).all()
               if _has(r"\b" + re.escape(m.name.replace(" Market", "").lower()) + r"\b", text)]
    products = [p for p in db.query(Product).all()
                if _find_terms(text, [p.name] + PRODUCT_ALIASES.get(p.name, []))]

    if context and not districts and not products and not wants_forecast_explanation(text, context) and wants_followup(text):
        reply, sources = followup_answer(db, context, text)
        result = done(reply, sources, "forecast_followup")
        result["context"] = context
        return result
    
    if _has(r"\b(real|fake|demo|synthetic|reliable|trust|accurate)\b", text):
        verified = db.query(PriceObservation).filter_by(status="verified").count()
        demo_prices = db.query(PriceObservation).filter_by(status="verified", is_synthetic=True).count()
        demo_cpi = db.query(OfficialSeries).join(DataSource).filter(DataSource.is_synthetic.is_(True)).count()
        total_cpi = db.query(OfficialSeries).count()
        reply = (f"Market prices: {verified} verified observations, of which {demo_prices} are SYNTHETIC "
                 "demo values for testing the interface, not real Rwandan prices.\n"
                 f"CPI category series: {demo_cpi} of {total_cpi} are SYNTHETIC demo series.\n"
                 "Headline inflation is calculated from the NISR CPI table (All Rwanda). Check the Sources tab "
                 "for the verification status of each dataset.")
        return done(reply, ["Data sources"], "data_status")

    if wants_forecast_explanation(text, context):
        result = done(forecast_explanation(), [SOURCE_FORECAST], "forecast_explanation")
        result["context"] = context
        return result
    if wants_forecast(text) and wants_climate(text):
        reply, sources, ctx = forecast_answer(db, districts[0] if districts else None, text)
        result = done(reply, sources, "forecast")
        if ctx:
            result["context"] = ctx
        return result
        
    if wants_climate(text) and districts:
        return done(*climate_answer(db, districts[0] if districts else None, requested_year(text)),
                    "climate")

    indicator_keys = match_indicators(text)
    if indicator_keys:
        reply, sources = indicator_answer(db, indicator_keys, districts[0] if districts else None,
                                          requested_year(text), requested_season(text))
        return done(reply, sources, "indicator")

    if products and (wants_explanation(text) or parse_period(text)):
        product = products[0]
        obs = _verified_obs(db, product.id)
        market = markets[0].name if markets else None
        reply = price_period_answer(db, product, obs, parse_period(text), wants_explanation(text), market)
        return done(reply, ["Verified market prices"], "price_period")

    if products and not _has(r"\b(critical|red|medium|yellow|green|good|zone|zones|map)\b", text):
        if len(districts) > 1:  # e.g. "compare irish potatoes in huye and musanze"
            blocks = [_product_reply(db, products[0], d)[0] for d in districts]
            return done("\n\n".join(blocks), ["Verified market prices"], "product_price")
        return done(*_product_reply(db, products[0], districts[0] if districts else
                                    (markets[0].district if markets else None)), "product_price")

    if not districts and _has(r"\b(what|mean|means|meaning|define|explain)\b", text) and \
            _has(r"\b(critical|medium|yellow|green|red|grey|gray|colou?r|colou?rs)\b", text):
        return done(colour_meaning(), ["District status map"], "colour_meaning")

    # "good" alone is not a district question ("recommend a good book"), so it does not trigger this branch
    if districts or _has(r"\b(critical|red|medium|yellow|green|zone|zones|map|district|districts)\b", text):
        report = district_report(db)
        if len(districts) == 1:
            name = districts[0]
            d = next(x for x in report["districts"] if x["name"] == name)
            if _has(r"\b(critical|red)\b", text) and _has(r"\b(is|in|zone)\b", text):
                return done(direct_critical_answer(name, d), ["District status map"], "district_status")
            return done(*_district_reply(report, name), "district_status")
        if len(districts) > 1:
            blocks = [_district_reply(report, d)[0] for d in districts]
            return done("\n\n".join(blocks), ["District status map"], "district_status")
        return done(*_status_summary(report), "district_status_summary")

    if _has(r"\b(inflation|cpi|headline|consumer price)\b", text):
        return done(*_inflation_reply(db), "inflation")

    if _has(r"\b(categor\w*|fastest|rising|increas\w*|highest)\b", text):
        return done(*_top_categories(db), "categories")

    if _has(r"\b(method\w*|formula|calculat\w*|threshold\w*|how is|how are|flag\w*)\b", text):
        return done(METHOD_TEXT, ["Methodology"], "methodology")

    if _has(r"\b(contribut\w*|submit\w*|report a price|add a price)\b", text):
        return done(CONTRIBUTE_TEXT, ["Contribute tab"], "contribute")

    if _has(r"\b(source|sources|dataset\w*|data|nisr)\b", text):
        return done(*_sources_reply(db), "sources")

    if _has(r"\b(price|prices|cost|how much)\b", text):
        names = ", ".join(p.name for p in db.query(Product).order_by(Product.name))
        return done(f"Which product would you like? I have prices for: {names}.", ["Market prices"], "ask_product")

    if _has(r"\b(hi|hello|hey|help|menu|what can you do|start)\b", text) or not raw:
        return done(HELP, [], "help")

    # No rule matched. Offer the closest question IsokoBot can answer, if one is clearly the best match.
    suggestion = suggest_question(raw)
    if suggestion:
        reply = f"Did you mean \"{suggestion}\"?"
        choices = [{"label": "Yes", "ask": suggestion}, {"label": "No", "ask": None}]
        return {**done(reply, [], "suggestion"), "choices": choices}
    if not _classified:  # the classifier never calls itself (its canonical questions are answered by rules)
        routed = _classifier_reply(db, raw)
        if routed is not None:
            return routed
    return done("can't respond to this!", [], "unknown")
