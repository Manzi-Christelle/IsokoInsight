"""Labelled questions for the IsokoBot intent classifier.

Each intent is a kind of answer IsokoBot gives. The classifier only has to choose the intent. The answer
itself still comes from the rules and the database, so the classifier can never invent a number.

Three sets of text:
  SEEDS      hand-written question templates. Placeholders such as {district} are filled at random to make
             training examples. One template in every four is held out for evaluation, so the evaluation
             uses phrasings the model never saw.
  CHALLENGE  questions written by the authors after the templates, in different words, never used for
             training. They are a stricter check than the held-out templates.
  CANONICAL  for intents that need no entity (no district, product or year), the exact question IsokoBot
             answers. Used when the classifier is confident, and offered as a Yes/No suggestion when it is
             fairly confident.

The authors wrote every example, so these sets are not an independent external test. The evaluation
report says so, and an external set should be added before the results are relied on.
"""
import random
import re

from ..districts import load_district_names
from ..reference import PRODUCTS

OUT_OF_SCOPE = "out_of_scope"

PRODUCT_NAMES = [name for name, _category, _unit in PRODUCTS]
PERIODS = ["2001 to 2005", "January 2010 to December 2012", "2008", "2015 to 2018",
           "1 January 2010 to 31 March 2011", "2020", "2022 to 2024", "2003 to 2009"]
INDICATOR_PHRASES = ["grain held in reserve", "grain reserve", "households within 1 km of a market",
                     "improved seeds use", "inorganic fertiliser use", "pesticide use", "food security score"]
ANIMALS = ["cows", "goats", "chickens", "pigs", "rabbits", "sheep"]

# Entity intents: the answer needs a district, product, period or year. IsokoBot asks for it.
CLARIFY = {
    "district_status": "Which district do you mean? For example: is Musanze in the critical zone?",
    "product_price": "Which product and market do you want? For example: price of maize flour in Huye.",
    "price_period": "Which product and period? For example: price of Irish potatoes from 2001 to 2005.",
    "indicator": "Which indicator, district and year? For example: grain held in reserve in Musanze in 2010.",
    "climate": "Which district and year do you want the rainfall or temperature for? "
               "For example: rainfall in Musanze in 2022.",
}

# Intents that need no entity: the exact question IsokoBot answers for them.
CANONICAL = {
    "critical_zone": "which districts are in the critical zone",
    "inflation": "what is headline inflation",
    "categories": "which categories are rising fastest",
    "colour_meaning": "what do the colours mean",
    "methodology": "how the numbers are calculated",
    "contribute": "how do I submit a price",
    "sources": "which data sources are used",
    "data_status": "are the prices real or synthetic",
    "ask_product": "what are the verified market prices",
    "help": "what can you do",
}

SEEDS = {
    "critical_zone": [
        "which districts are in the critical zone", "which districts are critical", "show me the red districts",
        "list the districts with high prices", "which areas have the highest food prices",
        "where are prices most above normal", "what districts are in the red zone", "name the critical districts",
        "are there any critical areas on the map", "show districts that are above the national median",
        "which districts have the most expensive food", "which places are in the danger zone for prices", "which places have the most expensive food in the country",
        "list the red areas on the price map", "are any districts above the critical threshold",
        "which districts exceed the price threshold"],
    "district_status": [
        "is {district} in the critical zone", "is {district} red or green", "how are food prices in {district}",
        "what is the status of {district}", "is {district} above the national median",
        "how expensive is food in {district}", "give me the colour for {district}",
        "tell me about {district} district prices", "are prices in {district} high",
        "how does {district} compare with the rest of the country", "what is happening with prices in {district}",
        "{district} district price status", "is {district} among the expensive districts",
        "has the price of food gone up in {district}", "is {district} one of the high price areas",
        "where does {district} stand on food prices", "are {district} markets expensive",
        "is food dearer in {district} than elsewhere"],
    "product_price": [
        "price of {product} in {district}", "how much is {product} at the market", "what does {product} cost in {district}",
        "{product} prices in {district}", "current price of {product}", "how much does a kilo of {product} sell for",
        "what is the market price of {product}", "compare {product} prices across markets", "where is {product} cheapest",
        "tell me the {product} rate in {district}", "what are {product} prices like", "{product} cost in {district} market"],
    "price_period": [
        "price of {product} from {period}", "explain the price graph of {product} from {period}",
        "{product} prices between {period}", "how did the price of {product} change over {period}",
        "show {product} price history for {period}", "what happened to {product} prices in {period}",
        "explain the {product} graph from {period}", "{product} price trend {period}",
        "how did {product} cost change in {period}", "graph of {product} prices for {period}",
        "{product} prices over the years {period}", "price history of {product} {period}"],
    "indicator": [
        "{indicator} in {district} in {year}", "how many {animal} in {district}", "{indicator} for {district} {year}",
        "what was {indicator} in {district} in {year}", "{indicator} {district}",
        "tell me {indicator} for {year} in {district}", "the value of {indicator} in {district} during {year}",
        "{district} {indicator} {year}", "how much {indicator} was in {district} in {year}",
        "{indicator} per district in {year}", "highest {indicator} in {year}",
        "which district has the most {indicator}"],
    "climate": [
        "rainfall in {district} in {year}", "how much rain did {district} get in {year}", "temperature in {district}",
        "how hot is {district}", "is {district} wetter than normal", "weather in {district} last year",
        "is {district} drier than usual", "what is the climate like in {district}",
        "temperatures in {district} during {year}", "was {year} a dry year in {district}",
        "how much rainfall fell in {district}", "rain figures for {district}",
        "how much did it rain in {district} in {year}", "what was the temperature in {district} in {year}",
        "was {year} wet in {district}", "how hot was {district} in {year}"],
    "categories": [
        "which categories are rising fastest", "what CPI categories went up the most",
        "which items have the biggest price increase", "what is rising fastest in the cpi",
        "which sectors have the highest price growth", "list the fastest rising categories",
        "which goods increased the most", "which expenditure groups rose most this year",
        "show the biggest price rises by category", "top price increases by category",
        "what are the highest rising CPI groups", "how fast are food prices going up compared with others"],
    "inflation": [
        "what is headline inflation", "what is the inflation rate", "how fast are prices rising in the country",
        "what is the cpi", "consumer price inflation this year", "what was inflation last month", "is inflation going up",
        "what is the general price index", "how much have prices gone up nationally",
        "what is the year on year change in prices", "tell me the national inflation figure",
        "how high is inflation in rwanda", "what is the inflation figure for this month",
        "how much did the cost of living rise", "what is the current year on year price change",
        "how much have prices gone up in a year"],
    "colour_meaning": [
        "what do the colours mean", "what does red mean on the map", "explain the colours on the district map",
        "what is the meaning of green", "what does yellow stand for", "what are the colour bands",
        "what does grey mean", "how do I read the map colours", "what is the critical zone colour",
        "what does the legend mean", "explain the colour scale", "what do the map shades mean"],
    "methodology": [
        "how are the numbers calculated", "what formula is used", "how is the percentage calculated",
        "explain the calculation method", "how do you work out the district index", "what thresholds do you use",
        "how are flags decided", "how was the price difference worked out", "what method is behind the colours",
        "how do you calculate the median", "explain how the figures are computed", "what are the rules for the review flags"],
    "contribute": [
        "how do I submit a price", "how can I add a market price", "I want to report a price I saw",
        "how do I contribute prices", "where can I enter a new price", "how do I send price data",
        "can I upload prices from my market", "how do farmers add prices", "submit a market observation",
        "how to report food prices", "how do I record a price", "where do I put in the price I checked"],
    "sources": [
        "what data sources are used", "where does the data come from", "which datasets does the app use",
        "who publishes the figures", "list the data sources", "what is the source of the inflation figures",
        "where is the information from", "which organisations provided the data", "show me the datasets",
        "what sources do you rely on", "is the data official", "where do the statistics come from"],
    "data_status": [
        "are these prices real", "is the data synthetic", "can I trust these figures", "are the prices demo values",
        "is this real data or fake data", "how reliable are the numbers", "are the figures accurate",
        "is the climate data real", "are the indicators real statistics", "is this demo data",
        "can I use these numbers in a report", "are these official numbers"],
    "ask_product": [
        "what are the market prices", "show me food prices", "what products do you have prices for",
        "which foods can I check", "list the products", "what food prices can I see",
        "which items are priced in the app", "give me the market price list", "what commodities do you track",
        "what can I look up about prices", "food prices please", "what products are covered"],
    "help": [
        "what can you do", "how do I use this app", "help me", "what questions can I ask",
        "show me what you can answer", "how does this work", "what are my options", "where do I start",
        "give me some examples of questions", "I need help", "what can I ask you", "how do I get started",
        "what does this assistant do", "what kind of questions do you answer", "show me the topics you know",
        "what information can I get here"],
    OUT_OF_SCOPE: [
        "what is the weather on mars", "tell me a joke", "who won the football match last night",
        "write a poem about love", "what is the capital of france", "translate hello into french",
        "recommend a good movie", "what time is it in tokyo", "how tall is mount everest",
        "who is the president of the united states", "write python code to sort a list",
        "what is the best phone to buy", "how do I fix my car engine", "what is the meaning of life",
        "tell me about black holes", "give me a recipe for chocolate cake", "how do I learn guitar",
        "what is the stock price of apple", "which movie won the oscar", "how many planets are there",
        "what is two plus two", "who painted the mona lisa", "how do I bake bread",
        "what are the rules of chess", "tell me a story about a dragon", "what is the score of the arsenal match",
        "how do I make a website", "what is bitcoin worth today", "where can I buy shoes", "can you sing a song",
        "what is the best laptop for students", "how do I cure a headache", "what is quantum physics",
        "who is the richest man in the world", "what is the population of china", "how do I get a passport",
        "write an email to my boss", "what should I wear today", "tell me about the history of rome",
        "how many calories are in an apple", "what is the best way to lose weight", "tell me about football players",
        "what is the time in london", "how do I cook a stew", "suggest a holiday destination", "what is love",
        "play a game with me", "how old is the earth", "what is the largest animal on earth",
        "write a song about rain", "what is the best book about history", "who invented the telephone",
        "how far is the moon", "what is a good name for my dog"],
}

# Written after the templates, in different words. Never used for training.
CHALLENGE = [
    ("which places are most in trouble for food costs", "critical_zone"),
    ("what regions are flagged red", "critical_zone"),
    ("how is Musanze doing on food prices", "district_status"),
    ("is Kayonza among the expensive areas", "district_status"),
    ("what is a kilo of rice fetching in Huye", "product_price"),
    ("avocado price right now", "product_price"),
    ("how did beans change from 2005 to 2010", "price_period"),
    ("explain the tomatoes chart for 2008 to 2009", "price_period"),
    ("how many goats did Gakenke have in 2012", "indicator"),
    ("grain stock in Rusizi in 2015", "indicator"),
    ("was Nyagatare dry in 2019", "climate"),
    ("how wet was Rubavu last year", "climate"),
    ("what is the cost of living growth rate", "inflation"),
    ("how much has the general index risen", "inflation"),
    ("which items are getting dearest fastest", "categories"),
    ("what do the shades on the map signify", "colour_meaning"),
    ("how did you decide the colour thresholds", "methodology"),
    ("I checked a price at my shop, where do I log it", "contribute"),
    ("who gives you the statistics", "sources"),
    ("are these numbers genuine or made up", "data_status"),
    ("what foods are on the list", "ask_product"),
    ("what sort of things can this assistant answer", "help"),
    ("recommend a good book", OUT_OF_SCOPE),
    ("what is the speed of light", OUT_OF_SCOPE),
    ("how do I reset my phone", OUT_OF_SCOPE),
    ("what's for dinner", OUT_OF_SCOPE),
    ("who is the best footballer", OUT_OF_SCOPE),
    ("write a haiku", OUT_OF_SCOPE),
    ("what is the square root of 81", OUT_OF_SCOPE),
    ("which bus goes to Nyamirambo", OUT_OF_SCOPE),
    ("why is the sky blue", OUT_OF_SCOPE),
    ("give me a workout plan", OUT_OF_SCOPE),
    ("what is machine learning", OUT_OF_SCOPE),
    ("how do I get a visa to uganda", OUT_OF_SCOPE),
]

HOLDOUT_EVERY = 4  # every fourth seed template is held out for evaluation


YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def normalise_entities(texts) -> list[str]:
    """Replace district, product, indicator, animal and year names with placeholders.

    The rules find the actual names. The classifier only needs the wording, so masking the names stops it
    from learning that, for example, 'Musanze' means 'district status'.
    """
    districts = sorted(load_district_names(), key=len, reverse=True)
    products = sorted((p.lower() for p in PRODUCT_NAMES), key=len, reverse=True)
    out = []
    for text in texts:
        s = " " + str(text).lower() + " "
        for name in districts:
            s = re.sub(r"\b" + re.escape(name.lower()) + r"\b", " districtname ", s)
        for name in products:
            s = re.sub(r"\b" + re.escape(name) + r"\b", " productname ", s)
        for phrase in sorted(INDICATOR_PHRASES, key=len, reverse=True):
            s = re.sub(r"\b" + re.escape(phrase.lower()) + r"\b", " indicatorname ", s)
        for animal in ANIMALS:
            s = re.sub(r"\b" + animal + r"\b", " animalname ", s)
        s = YEAR_RE.sub(" yearvalue ", s)
        out.append(" ".join(s.split()))
    return out


def _fill(template: str, rng: random.Random, districts: list[str]) -> str:
    out = template
    if "{district}" in out:
        out = out.replace("{district}", rng.choice(districts))
    if "{product}" in out:
        out = out.replace("{product}", rng.choice(PRODUCT_NAMES).lower())
    if "{period}" in out:
        out = out.replace("{period}", rng.choice(PERIODS))
    if "{year}" in out:
        out = out.replace("{year}", str(rng.randint(2000, 2025)))
    if "{indicator}" in out:
        out = out.replace("{indicator}", rng.choice(INDICATOR_PHRASES))
    if "{animal}" in out:
        out = out.replace("{animal}", rng.choice(ANIMALS))
    return out


def _typo(text: str, rng: random.Random) -> str:
    if len(text) < 4:
        return text
    i = rng.randrange(1, len(text) - 1)
    op = rng.choice(["delete", "replace", "swap"])
    if op == "delete":
        return text[:i] + text[i + 1:]
    if op == "replace":
        return text[:i] + rng.choice("abcdefghijklmnoprstuvwy") + text[i + 1:]
    return text[:i] + text[i + 1] + text[i] + text[i + 2:]


PREFIXES = ["", "", "", "please ", "hey, ", "can you tell me ", "quick question: "]


def _variants(template: str, rng: random.Random, n: int, districts: list[str]) -> list[str]:
    out: set[str] = set()
    attempts = 0
    while len(out) < n and attempts < n * 25:
        attempts += 1
        s = rng.choice(PREFIXES) + _fill(template, rng, districts)
        if rng.random() < 0.2:
            s = s.lower()
        if rng.random() < 0.3:
            s = _typo(s, rng)
        out.add(re.sub(r"\s+", " ", s).strip())
    return sorted(out)


def build(split: str, seed: int = 7) -> tuple[list[str], list[str]]:
    """Training examples ('train'), held-out examples ('holdout') or everything from the templates ('all')."""
    rng = random.Random(seed if split != "holdout" else seed + 1)
    districts = load_district_names()
    texts, labels = [], []
    for intent, templates in SEEDS.items():
        for i, template in enumerate(templates):
            held_out = i % HOLDOUT_EVERY == HOLDOUT_EVERY - 1
            if split == "train" and held_out:
                continue
            if split == "holdout" and not held_out:
                continue
            has_slot = bool(re.search(r"\{(district|product|period|year|indicator|animal)\}", template))
            for s in _variants(template, rng, 8 if has_slot else 4, districts):
                texts.append(s)
                labels.append(intent)
    return texts, labels


def challenge() -> tuple[list[str], list[str]]:
    return [t for t, _ in CHALLENGE], [y for _, y in CHALLENGE]
