from datetime import date
from types import SimpleNamespace as NS

from app import analytics


def test_pct_change_matches_blueprint_example():
    # Market A 600 vs Market B 500 -> A is 20% more expensive
    assert analytics.pct_change(600, 500) == 20.0
    assert analytics.pct_change(5, 0) is None


def test_mom_and_yoy():
    pts = [(date(2025, m, 1), 100 + m) for m in range(1, 13)] + [(date(2026, 1, 1), 202)]
    out = analytics.add_changes(pts)
    assert out[0]["mom_pct"] is None
    assert out[-1]["yoy_pct"] == round((202 - 101) / 101 * 100, 2)


def test_anomaly_detection_flags_jump_only():
    pts = [(date(2024 + (m // 12), m % 12 + 1, 1), 100 * 1.005 ** m) for m in range(30)]
    jump = pts[-1][1] * 1.2
    pts.append((date(2026, 7, 1), jump))
    flags = analytics.detect_series_anomalies(pts, threshold_pct=5)
    assert [f["period"] for f in flags] == [date(2026, 7, 1)]
    assert analytics.detect_series_anomalies(pts[:-1], threshold_pct=5) == []


def _obs(market_id, price, unit, d, status="verified"):
    return NS(market_id=market_id, market=NS(name=f"M{market_id}", district="D"), price_rwf=price,
              unit=unit, observed_on=d, status=status, is_synthetic=False)


def test_compare_never_mixes_units_and_ignores_unverified():
    obs = [_obs(1, 500, "kg", date(2026, 9, 1)), _obs(2, 600, "kg", date(2026, 9, 2)),
           _obs(3, 40000, "sack_100kg", date(2026, 9, 2)),
           _obs(4, 100, "kg", date(2026, 9, 2), status="pending")]
    res = analytics.compare_markets(obs)
    assert set(res) == {"kg", "sack_100kg"}
    assert res["kg"]["markets_compared"] == 2          # pending market 4 excluded
    assert res["kg"]["rows"][1]["diff_pct_vs_cheapest"] == 20.0
    assert res["sack_100kg"]["markets_compared"] == 1


def test_compare_uses_latest_price_per_market():
    obs = [_obs(1, 500, "kg", date(2026, 8, 1)), _obs(1, 550, "kg", date(2026, 9, 1))]
    assert analytics.compare_markets(obs)["kg"]["rows"][0]["price_rwf"] == 550
