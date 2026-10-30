from datetime import date

from .conftest import approve, register


def sample_price(**kw):
    base = {"product_id": 1, "market_id": 1, "price_rwf": 600, "unit": "kg",
            "observed_on": date.today().isoformat(), "collection_method": "enumerator visit"}
    base.update(kw)
    return base


def test_roles_are_accepted_and_approval_rules_apply(client):
    cust = register(client, "cust@test.rw", "customer")
    assert cust.status_code == 201 and cust.json()["status"] == "active" and cust.json()["access_token"]
    farm = register(client, "farm@test.rw", "farmer_seller")
    assert farm.json()["status"] == "active"
    for role, email in [("enumerator", "enum@test.rw"), ("nisr", "nisr@test.rw")]:
        r = register(client, email, role, organisation="NISR" if role == "nisr" else None)
        assert r.status_code == 201
        assert r.json()["status"] == "pending" and r.json()["access_token"] is None
        # Pending accounts cannot sign in.
        assert client.post("/api/auth/login", data={"username": email, "password": "RolePass12345"}).status_code == 403


def test_unknown_role_is_rejected(client):
    assert register(client, "bad@test.rw", "minister").status_code == 422


def test_customer_reads_and_downloads_but_cannot_submit_or_export_full_data(client, admin):
    h = register(client, "cust2@test.rw", "customer").json()["access_token"]
    headers = {"Authorization": "Bearer " + h}
    assert client.get("/api/prices").status_code == 200          # public verified prices
    assert client.get("/api/prices/export.csv", headers=headers).status_code == 200
    assert client.post("/api/prices", json=sample_price(), headers=headers).status_code == 403
    assert client.get("/api/nisr/dataset.csv", headers=headers).status_code == 403
    assert client.get("/api/nisr/statistics", headers=headers).status_code == 403
    assert client.get("/api/me/submissions", headers=headers).status_code == 403
    assert client.get("/api/admin/users", headers=headers).status_code == 403


def test_farmer_seller_submits_and_sees_own_status_only(client, admin):
    reg = register(client, "f2@test.rw", "farmer_seller")
    headers = {"Authorization": "Bearer " + reg.json()["access_token"]}
    assert client.post("/api/prices", json=sample_price(price_rwf=640), headers=headers).status_code == 201
    mine = client.get("/api/me/submissions", headers=headers).json()
    assert len(mine) == 1 and mine[0]["status"] == "pending"
    assert client.post("/api/admin/observations/%d/review" % mine[0]["id"], json={"action": "approve"},
                       headers=headers).status_code == 403   # cannot verify its own price


def test_enumerator_needs_approval_then_can_submit(client, admin):
    register(client, "enum2@test.rw", "enumerator")
    assert client.post("/api/auth/login", data={"username": "enum2@test.rw", "password": "RolePass12345"}).status_code == 403
    headers = approve(client, admin, "enum2@test.rw")
    assert client.post("/api/prices", json=sample_price(price_rwf=650), headers=headers).status_code == 201


def test_nisr_needs_approval_then_exports_full_dataset_and_statistics(client, admin):
    register(client, "nisr2@test.rw", "nisr", organisation="NISR")
    # Create a pending record so the full export has something that is NOT verified.
    f = register(client, "f3@test.rw", "farmer_seller").json()["access_token"]
    client.post("/api/prices", json=sample_price(price_rwf=9999), headers={"Authorization": "Bearer " + f})
    headers = approve(client, admin, "nisr2@test.rw")

    full = client.get("/api/nisr/dataset.csv", headers=headers)
    assert full.status_code == 200
    lines = full.text.strip().splitlines()
    assert lines[0].startswith("id,product,unit,market,district,price_rwf")
    assert any(",pending," in l for l in lines[1:])            # pending records are included for NISR
    assert "@" not in full.text                                # no submitter identities

    stats = client.get("/api/nisr/statistics", headers=headers).json()
    assert stats["verified_observations"] > 0
    assert all(p["min_rwf"] <= p["median_rwf"] <= p["max_rwf"] for p in stats["products"])
    assert stats["contains_synthetic"] is True                 # demo data is declared
    assert stats["districts"]["status_counts"]["no_data"] == 0   # every district has demo prices
    assert stats["monthly_medians"] and "month" in stats["monthly_medians"][0]
    assert stats["official"]["headline"][0]["value"] == 15.9


def test_admin_manages_accounts_and_cannot_lock_self_out(client, admin):
    users = client.get("/api/admin/users", headers=admin).json()
    me = next(u for u in users if u["email"] == "admin@test.rw")
    assert client.patch(f"/api/admin/users/{me['id']}", json={"status": "disabled"}, headers=admin).status_code == 422
    assert client.patch(f"/api/admin/users/{me['id']}", json={"role": "customer"}, headers=admin).status_code == 422
    assert client.patch("/api/admin/users/99999", json={"status": "active"}, headers=admin).status_code == 404


def test_disabled_account_is_blocked_immediately(client, admin):
    reg = register(client, "gone@test.rw", "customer").json()["access_token"]
    headers = {"Authorization": "Bearer " + reg}
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    uid = next(u["id"] for u in client.get("/api/admin/users", headers=admin).json() if u["email"] == "gone@test.rw")
    client.patch(f"/api/admin/users/{uid}", json={"status": "disabled"}, headers=admin)
    assert client.get("/api/auth/me", headers=headers).status_code == 403
    assert client.post("/api/auth/login", data={"username": "gone@test.rw", "password": "RolePass12345"}).status_code == 403


def test_me_reports_role_and_permissions(client):
    r = register(client, "me2@test.rw", "farmer_seller", name="Jean Claude").json()
    me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + r["access_token"]}).json()
    assert me["role"] == "farmer_seller" and me["full_name"] == "Jean Claude"
    assert "submit_price" in me["permissions"] and "export_full_dataset" not in me["permissions"]


def test_migration_turns_contributor_into_farmer_seller(tmp_path):
    from sqlalchemy import create_engine, text
    from app.db import ensure_schema
    eng = create_engine(f"sqlite:///{tmp_path}/old.db")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(200), password_hash VARCHAR(300), role VARCHAR(20), created_at DATETIME)"))
        c.execute(text("INSERT INTO users (email, password_hash, role) VALUES ('old@x.rw', 'x', 'contributor')"))
    ensure_schema(eng)
    ensure_schema(eng)  # running twice is harmless
    with eng.connect() as c:
        row = c.execute(text("SELECT role, status FROM users")).one()
    assert tuple(row) == ("farmer_seller", "active")
