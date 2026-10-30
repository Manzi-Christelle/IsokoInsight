import os
import shutil
import tempfile

# Use an isolated throw-away database for the whole test run (must be set before importing app).
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["ADMIN_EMAIL"] = "admin@test.rw"
os.environ["ADMIN_PASSWORD"] = "AdminPass12345"
os.environ["APP_ENV"] = "development"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_demo, seed_reference  # noqa: E402


_TEMPLATE = os.path.join(_tmp, "template.db")
_TEST_DB = os.path.join(_tmp, "test.db")


@pytest.fixture(scope="session", autouse=True)
def _seeded_template():
    """Seed the reference data and the demo data once, then give each test a fresh copy of that database.

    Seeding 134,000 demonstration prices takes a few seconds, so doing it for every test would be slow.
    """
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_reference(db)
        seed_demo(db)
    engine.dispose()
    shutil.copyfile(_TEST_DB, _TEMPLATE)
    yield


@pytest.fixture()
def client(_seeded_template):
    engine.dispose()
    shutil.copyfile(_TEMPLATE, _TEST_DB)
    with TestClient(app) as c:
        yield c


def login(client, email, password):
    r = client.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture()
def admin(client):
    return login(client, "admin@test.rw", "AdminPass12345")


def register(client, email, role, password="RolePass12345", name="Test Person", organisation=None):
    body = {"email": email, "password": password, "full_name": name, "role": role}
    if organisation:
        body["organisation"] = organisation
    return client.post("/api/auth/register", json=body)


def approve(client, admin_headers, email):
    users = client.get("/api/admin/users", headers=admin_headers).json()
    uid = next(u["id"] for u in users if u["email"] == email)
    r = client.patch(f"/api/admin/users/{uid}", json={"status": "active"}, headers=admin_headers)
    assert r.status_code == 200
    return login(client, email, "RolePass12345")


@pytest.fixture()
def contributor(client):
    r = register(client, "c@test.rw", "farmer_seller", password="ContribPass123")
    assert r.status_code == 201
    return {"Authorization": "Bearer " + r.json()["access_token"]}
