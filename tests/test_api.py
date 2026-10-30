from datetime import date, timedelta

from .conftest import login


def payload(**kw):
    base = {"product_id": 1, "market_id": 1, "price_rwf": 500, "unit": "kg",
            "observed_on": date.today().isoformat(), "collection_method": "enumerator visit"}
    base.update(kw)
    return base


def test_health_and_reference_data(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert len(client.get("/api/products").json()) == 14  # 6 original + 8 added
    assert len(client.get("/api/markets").json()) == 30  # 4 original + 4 added + 22 for district coverage


def test_demo_prices_are_labelled_synthetic(client):
    rows = client.get("/api/prices").json()
    assert rows and all(r["is_synthetic"] for r in rows)
    sources = client.get("/api/sources").json()
    assert any(s["is_synthetic"] for s in sources)
    assert any("NISR" in s["publisher"] and not s["is_synthetic"] for s in sources)


def test_official_statistics_have_attribution_and_flags(client):
    inds = client.get("/api/official/indicators").json()
    headline = next(i for i in inds if i["name"].startswith("Headline"))
    assert headline["source"] and headline["value"] == 15.9 and headline["period"] == "2026-08-01"
    series = client.get("/api/official/series").json()
    assert "not market prices" in series["note"]
    detail = client.get("/api/official/series/00-general-index-cpi").json()
    assert detail["source"]["name"] and detail["source"]["is_synthetic"] is False  # real NISR table
    assert len(detail["data"]) == 211 and detail["data"][-1]["period"] == "2026-08-01"
    assert isinstance(detail["review_flags"], list)


def test_submission_requires_login(client):
    assert client.post("/api/prices", json=payload()).status_code == 401


def test_invalid_submissions_rejected(client, contributor):
    assert client.post("/api/prices", json=payload(price_rwf=-5), headers=contributor).status_code == 422
    assert client.post("/api/prices", json=payload(price_rwf=0), headers=contributor).status_code == 422
    future = (date.today() + timedelta(days=3)).isoformat()
    assert client.post("/api/prices", json=payload(observed_on=future), headers=contributor).status_code == 422
    assert client.post("/api/prices", json=payload(unit="sack_100kg"), headers=contributor).status_code == 422
    assert client.post("/api/prices", json=payload(market_id=999), headers=contributor).status_code == 422


def test_pending_is_hidden_until_verified(client, contributor, admin):
    r = client.post("/api/prices", json=payload(price_rwf=777), headers=contributor)
    assert r.status_code == 201 and r.json()["status"] == "pending"
    obs_id = r.json()["id"]
    assert all(row["id"] != obs_id for row in client.get("/api/prices?limit=1000").json())

    assert client.post(f"/api/admin/observations/{obs_id}/review", json={"action": "approve"},
                       headers=contributor).status_code == 403
    ok = client.post(f"/api/admin/observations/{obs_id}/review", json={"action": "approve", "note": "ok"}, headers=admin)
    assert ok.status_code == 200
    assert any(row["id"] == obs_id and row["status"] == "verified" for row in client.get("/api/prices?limit=1000").json())
    assert client.post(f"/api/admin/observations/{obs_id}/review", json={"action": "approve"}, headers=admin).status_code == 409


def test_correct_and_reject_are_audited(client, contributor, admin):
    a = client.post("/api/prices", json=payload(price_rwf=900), headers=contributor).json()["id"]
    b = client.post("/api/prices", json=payload(price_rwf=901, product_id=2), headers=contributor).json()["id"]
    assert client.post(f"/api/admin/observations/{a}/review", json={"action": "correct"}, headers=admin).status_code == 422
    client.post(f"/api/admin/observations/{a}/review", json={"action": "correct", "new_price_rwf": 450, "note": "typo"}, headers=admin)
    client.post(f"/api/admin/observations/{b}/review", json={"action": "reject"}, headers=admin)
    audit = client.get("/api/admin/audit", headers=admin).json()
    corr = next(x for x in audit if x["action"] == "correct")
    assert (corr["old_price_rwf"], corr["new_price_rwf"]) == (900, 450)
    assert any(x["action"] == "reject" for x in audit)
    assert client.get("/api/admin/audit").status_code == 401


def test_large_change_creates_review_flag_not_rejection(client, contributor, admin):
    r = client.post("/api/prices", json=payload(price_rwf=9000), headers=contributor).json()
    assert r["flagged_for_review"] is True and r["status"] == "pending"
    alerts = client.get("/api/admin/alerts", headers=admin).json()
    assert alerts and "does not mean a shortage" in alerts[0]["message"]


def test_compare_endpoint_groups_by_unit_and_marks_demo(client):
    res = client.get("/api/prices/compare?product_id=1").json()
    assert set(res["groups_by_unit"]) == {"kg"}
    assert res["contains_synthetic"] is True
    assert res["groups_by_unit"]["kg"]["markets_compared"] == 30
    assert client.get("/api/prices/compare?product_id=999").status_code == 404


def test_public_signup_cannot_create_admin(client):
    r = client.post("/api/auth/register", json={"email": "x@test.rw", "password": "SomePassword1",
                                                "full_name": "Xavier", "role": "admin"})
    assert r.status_code == 422  # administrators are never self-registered
    assert client.post("/api/auth/login", data={"username": "x@test.rw", "password": "SomePassword1"}).status_code == 401
    assert client.post("/api/auth/login", data={"username": "x@test.rw", "password": "wrong"}).status_code == 401


def test_csv_export_and_dashboard_served(client, contributor):
    assert client.get("/api/prices/export.csv?product_id=1").status_code == 401  # sign-in required
    r = client.get("/api/prices/export.csv?product_id=1", headers=contributor)
    assert r.status_code == 200 and r.text.startswith("id,product,market")
    page = client.get("/")
    assert page.status_code == 200 and "IsokoInsight" in page.text


def test_cpi_upload_requires_admin_and_imports(client, admin, contributor):
    csv_text = "Title\nPeriod,Test Index A,Test Index B\n" + "\n".join(f"Jan-{2010 + i},{100 + i},{90 + i}" for i in range(8))
    files = {"file": ("cpi.csv", csv_text.encode(), "text/csv")}
    q = "?name=Test CPI&period=2010-2017"
    assert client.post("/api/admin/import-cpi" + q, files=files, headers=contributor).status_code == 403
    r = client.post("/api/admin/import-cpi" + q, files={"file": ("cpi.csv", csv_text.encode(), "text/csv")}, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["series_created"] == 2 and r.json()["values_added"] == 16
    assert any(s["source"] == "Test CPI" for s in client.get("/api/official/series").json()["series"])
