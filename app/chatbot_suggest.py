"""IsokoBot wording suggestions: a pair hidden Markov model decoded with the Viterbi algorithm.

IsokoBot uses this only when no answer rule matches. It looks for the question the person most probably
meant, asks "Did you mean ...?" with Yes and No buttons, and answers that question if they choose Yes.

How the match works
  * The typed text is aligned character by character with each known phrase (the CATALOGUE below).
  * The alignment is a pair hidden Markov model with three hidden states:
      MATCH   the typed character is the phrase character, or a typo of it;
      INSERT  the person typed an extra character;
      DELETE  the person left out a character of the phrase.
  * The Viterbi algorithm (dynamic programming, time proportional to len(typed) x len(phrase)) finds
    the most probable path through these states.
  * The probability per character is the similarity score, from 0 to 1.

Optimisation
  * Exact matches return at once, without the dynamic programme.
  * Phrases that share few character trigrams with the typed text are skipped before the dynamic programme.
  * A suggestion is made only when the best catalogue entry is clearly ahead of the next one, so
    unrelated text gets "can't respond to this!" instead of a wrong guess.

Every catalogue question must route to a real answer in chatbot.answer(). tests/test_chatbot_suggest.py
checks this.
"""
import math
import re

# Hand-set probabilities. Calibrated with tests/test_chatbot_suggest.py.
P_SAME = 0.95      # MATCH emits the same character
P_TYPO = 0.05      # MATCH emits a different character (a typo)
P_STAY = 0.95      # MATCH follows any state
P_GAP = 0.10       # entering or extending an INSERT or DELETE step
P_EXTRA = 1 / 27   # INSERT emits one of the 26 letters or a space

MIN_SCORE = 0.5    # the best entry must reach this similarity (unrelated text scores about 0.2 or less)
MIN_MARGIN = 0.1   # and beat the next best entry by at least this much (so ambiguous wording gets no guess)
MIN_LENGTH = 4     # shorter text is too little to match

CATALOGUE = [
    {"ask": "the number of households within 1 km from the market", "phrases": [
        "distance to the market", "distance from the market", "households within 1 km of the market",
        "households near the market", "how far from the market", "market access",
        "households within 1km", "number of households within 1 km"]},
    {"ask": "the grain held in reserve in a district", "phrases": [
        "grain held in reserve", "grain reserve", "grains in reserve", "grain stock", "stored grain"]},
    {"ask": "the number of cattle kept in a district", "phrases": [
        "cattle kept", "cows kept", "how many cows", "number of cows", "cattle in a district"]},
    {"ask": "the number of goats kept in a district", "phrases": [
        "goats kept", "how many goats", "number of goats", "goat keeping"]},
    {"ask": "the number of chickens kept in a district", "phrases": [
        "chickens kept", "how many chickens", "number of chickens", "poultry kept"]},
    {"ask": "the number of pigs kept in a district", "phrases": [
        "pigs kept", "how many pigs", "number of pigs", "pig keeping"]},
    {"ask": "the number of rabbits kept in a district", "phrases": [
        "rabbits kept", "how many rabbits", "number of rabbits", "rabbit keeping"]},
    {"ask": "the number of sheep kept in a district", "phrases": [
        "sheep kept", "how many sheep", "number of sheep", "sheep keeping"]},
    {"ask": "the share of farmers using improved seeds in a season", "phrases": [
        "improved seeds used", "use of improved seeds", "improved seed use"]},
    {"ask": "the share of farmers using inorganic fertiliser in a season", "phrases": [
        "inorganic fertiliser use", "inorganic fertilizer use", "chemical fertiliser use"]},
    {"ask": "the share of farmers using organic fertiliser in a season", "phrases": [
        "organic fertiliser use", "organic fertilizer use", "manure use"]},
    {"ask": "the share of farmers using pesticides in a season", "phrases": [
        "pesticides used", "pesticide use", "use of pesticides"]},
    {"ask": "the food security score", "phrases": [
        "food security score", "food security index", "security score"]},
    {"ask": "what is headline inflation", "phrases": [
        "headline inflation", "inflation rate", "general inflation", "cpi inflation"]},
    {"ask": "which categories are rising fastest", "phrases": [
        "categories rising fastest", "fastest rising categories", "highest rising categories"]},
    {"ask": "which districts are in the critical zone", "phrases": [
        "critical zone", "critical districts", "red districts", "districts in critical zone"]},
    {"ask": "what do the colours mean", "phrases": [
        "meaning of the colours", "colour meaning", "what do the colours mean", "what is red yellow green"]},
    {"ask": "how are the numbers calculated", "phrases": [
        "how is it calculated", "calculation method", "formula", "how the numbers are calculated"]},
    {"ask": "how do I submit a price", "phrases": [
        "submit a price", "add a price", "report a price", "contribute prices"]},
    {"ask": "which data sources are used", "phrases": [
        "data sources", "where does the data come from", "what data is used", "source of data"]},
    {"ask": "what are the verified market prices", "phrases": [
        "market prices", "food prices", "price of a product", "product prices", "how much does it cost"]},
]


def _normalise(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).split())


def _trigrams(s: str) -> set[str]:
    padded = f"  {s} "
    return {padded[i:i + 3] for i in range(len(padded) - 2)}


def _may_match(typed: str, phrase: str) -> bool:
    """Cheap pre-check: skip phrases with almost no characters in common (optimisation)."""
    a, b = _trigrams(typed), _trigrams(phrase)
    return len(a & b) / len(a | b) >= 0.2


def _viterbi(typed: str, target: str) -> float:
    """Log-probability of the most probable alignment of typed (observed) against target (hidden)."""
    n, m = len(typed), len(target)
    lp_same, lp_typo = math.log(P_SAME), math.log(P_TYPO)
    lp_stay, lp_gap, lp_extra = math.log(P_STAY), math.log(P_GAP), math.log(P_EXTRA)
    neg = float("-inf")
    # match[i][j]: best log-probability after typed[:i] and target[:j], the last step being MATCH.
    # ins[i][j]:   the last step was INSERT (consumed typed[i-1]).
    # dele[i][j]:  the last step was DELETE (consumed target[j-1]).
    match = [[neg] * (m + 1) for _ in range(n + 1)]
    ins = [[neg] * (m + 1) for _ in range(n + 1)]
    dele = [[neg] * (m + 1) for _ in range(n + 1)]
    match[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            if i and j:
                emit = lp_same if typed[i - 1] == target[j - 1] else lp_typo
                match[i][j] = max(match[i - 1][j - 1], ins[i - 1][j - 1], dele[i - 1][j - 1]) + lp_stay + emit
            if i:
                ins[i][j] = max(match[i - 1][j], ins[i - 1][j], dele[i - 1][j]) + lp_gap + lp_extra
            if j:
                dele[i][j] = max(match[i][j - 1], ins[i][j - 1], dele[i][j - 1]) + lp_gap
    return max(match[n][m], ins[n][m], dele[n][m])


def similarity(typed: str, target: str) -> float:
    """0 to 1: the per-character probability of the best alignment."""
    if typed == target:
        return 1.0
    if not typed or not target:
        return 0.0
    return math.exp(_viterbi(typed, target) / max(len(typed), len(target)))


def suggest_question(text: str) -> str | None:
    """The catalogue question the person most probably meant, or None if no entry is clearly the best."""
    typed = _normalise(text)
    if len(typed) < MIN_LENGTH:
        return None
    ranked = []
    for entry in CATALOGUE:
        best = max((similarity(typed, p) for p in entry["phrases"] + [entry["ask"]]
                    if _may_match(typed, p)), default=0.0)
        ranked.append((best, entry["ask"]))
    ranked.sort(reverse=True)
    (top, ask), (second, _) = ranked[0], ranked[1]
    if top >= MIN_SCORE and top - second >= MIN_MARGIN:
        return ask
    return None
