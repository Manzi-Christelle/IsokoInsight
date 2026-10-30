"""IsokoBot answers about a product's price over a period, and explains the price history graph.

A period is a single year ("in 2010") or a range ("from 2001 to 2005"). Only verified prices are used, and
the same dates as the price search apply: outside the covered range the answer is "No data found".
"""
import re
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from .config import settings
from .models import Product

NO_DATA = "No data found"
_YEAR = r"(?:19|20)\d{2}"


_MONTHS = {}
for _i in range(1, 13):
    _name = date(2000, _i, 1).strftime("%B").lower()
    _MONTHS[_name] = _i
    _MONTHS[_name[:3]] = _i
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_DATE_PATTERNS = [
    # 2010-01-01
    (rf"\b((?:19|20)\d{{2}})-(\d{{1,2}})-(\d{{1,2}})\b", "ymd"),
    # 09/14/2000 (month first, as in the date pickers; day first if the first number is above 12)
    (r"\b(\d{1,2})/(\d{1,2})/((?:19|20)\d{2})\b", "slash"),
    # 1 January 2010, 1st Jan 2010
    (rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_RE})\.?,?\s+((?:19|20)\d{{2}})\b", "dmy_words"),
    # January 1, 2010
    (rf"\b({_MONTH_RE})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+((?:19|20)\d{{2}})\b", "mdy_words"),
    # March 2026
    (rf"\b({_MONTH_RE})\.?,?\s+((?:19|20)\d{{2}})\b", "my_words"),
]


def _mention(kind, m):
    """Return (start, end) dates for one matched date mention."""
    g = m.groups()
    try:
        if kind == "ymd":
            d = date(int(g[0]), int(g[1]), int(g[2]))
            return d, d
        if kind == "slash":
            a, b, y = int(g[0]), int(g[1]), int(g[2])
            d = date(y, b, a) if a > 12 else date(y, a, b)
            return d, d
        if kind == "dmy_words":
            d = date(int(g[2]), _MONTHS[g[1].lower()], int(g[0]))
            return d, d
        if kind == "mdy_words":
            d = date(int(g[2]), _MONTHS[g[0].lower()], int(g[1]))
            return d, d
        if kind == "my_words":
            month, y = _MONTHS[g[0].lower()], int(g[1])
            last = (date(y + (month == 12), month % 12 + 1, 1) - timedelta(days=1))
            return date(y, month, 1), last
    except ValueError:
        return None
    return None


def parse_period(text: str) -> tuple[date, date] | None:
    """The period a question asks about: two dates ("from X to Y"), one date, a month, or a year.

    Returns (first day, last day) inclusive, or None when the question names no period.
    """
    text = text.lower()
    mentions, spans = [], []
    for pattern, kind in _DATE_PATTERNS:  # most specific patterns first; overlapping matches are ignored
        for m in re.finditer(pattern, text):
            if any(m.start() < b and a < m.end() for a, b in spans):
                continue
            found = _mention(kind, m)
            if found:
                mentions.append((m.start(), found))
                spans.append(m.span())

    def inside(pos):
        return any(a <= pos < b for a, b in spans)

    for m in re.finditer(r"\b((?:19|20)\d{2})\b", text):  # plain years, unless part of a full date
        if not inside(m.start()):
            y = int(m.group(1))
            mentions.append((m.start(), (date(y, 1, 1), date(y, 12, 31))))
    if not mentions:
        return None
    mentions.sort(key=lambda x: x[0])
    periods = [found for _, found in mentions]
    if len(periods) == 1:
        return periods[0]
    first, last = periods[0][0], periods[1][1]
    return (min(first, last), max(first, last))


def wants_explanation(text: str) -> bool:
    return bool(re.search(r"\b(explain|explanation|meaning|what does|how (do|to) (i )?read|read the|graph|chart)\b", text))


def _date_label(d: date) -> str:
    return d.strftime("%d %B %Y").lstrip("0")


def price_period_answer(db: Session, product: Product, obs: list, period: tuple[date, date] | None,
                        explain: bool, market_name: str | None = None) -> str:
    start, end = settings.price_range_start, settings.price_range_end
    lines = []
    if explain:
        lines.append(
            f"The price history graph shows verified {product.name} prices at each market, in Rwandan francs "
            f"(RWF) per {product.standard_unit}. Each coloured line is one market, and the legend under the "
            "graph names them. Each point is a verified observation date; gaps mean no verified price was recorded "
            "that day. The From and To dates limit both the graph and the table, so only the period you choose is "
            f"shown. Dates can be chosen from {_date_label(start)} to {_date_label(end)}.")
    if period:
        a, b = period
        if b < start or a > end:
            return "\n".join(lines + [f"{NO_DATA} for {a.year} to {b.year}. Prices cover "
                                     f"{_date_label(start)} to {_date_label(end)}."])
        clamped = a < start or b > end
        a, b = max(a, start), min(b, end)
        chosen = [o for o in obs if a <= o.observed_on <= b and (not market_name or o.market.name == market_name)]
        if not chosen:
            return "\n".join(lines + [f"{NO_DATA} for {product.name} between {a.year} and {b.year}."])
        by_market = defaultdict(list)
        for o in sorted(chosen, key=lambda o: o.observed_on):
            by_market[o.market.name].append(o)
        lines.append(f"{product.name}, {_date_label(a)} to {_date_label(b)} (RWF per {product.standard_unit}):")
        if clamped:
            lines.append(f"The price data covers {_date_label(start)} to {_date_label(end)}, so the answer uses those dates.")
        changes, first_last = [], []
        for name, rows in sorted(by_market.items()):
            first, last = rows[0], rows[-1]
            prices = [r.price_rwf for r in rows]
            pct = (last.price_rwf - first.price_rwf) / first.price_rwf * 100 if first.price_rwf else None
            if pct is not None:
                changes.append(pct)
            first_last.append((name, last.price_rwf))
            if market_name or len(by_market) <= 3:
                lines.append(f"- {name}: {first.price_rwf:,} on {first.observed_on} to {last.price_rwf:,} on "
                             f"{last.observed_on} ({pct:+.1f}%), lowest {min(prices):,}, highest {max(prices):,}.")
        if not market_name and len(by_market) > 3:
            avg = sum(changes) / len(changes) if changes else 0
            high = max(first_last, key=lambda x: x[1])
            low = min(first_last, key=lambda x: x[1])
            lines.append(f"Across {len(by_market)} markets, the price moved {avg:+.1f}% on average from the first "
                         f"to the last verified date. Highest at the end: {high[0]} ({high[1]:,}). "
                         f"Lowest at the end: {low[0]} ({low[1]:,}).")
        if any(o.is_synthetic for o in chosen):
            lines.append("DEMO DATA: these prices are synthetic examples, not real market prices.")
    return "\n".join(lines)
