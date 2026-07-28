"""Auth tests — login, logout, wrong password, per-user data isolation."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def authed_client(mock_llm_available, reset_stores):
    """A separate TestClient logged in as the seeded admin."""
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert r.status_code == 200 and r.json()["ok"]
        yield c


def test_login_success(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "username": "admin"}
    assert "productiq_user" in r.cookies


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["ok"] is False


def test_me_unauthenticated(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["authenticated"] is False


def test_me_authenticated(authed_client):
    r = authed_client.get("/api/auth/me")
    assert r.json()["authenticated"] is True
    assert r.json()["username"] == "admin"


def test_logout_invalidates(authed_client):
    r = authed_client.post("/api/auth/logout")
    assert r.json()["ok"] is True
    r2 = authed_client.get("/api/auth/me")
    assert r2.json()["authenticated"] is False


def test_routes_open_for_anonymous(client):
    """Optional login: anonymous users still get the app."""
    r = client.get("/api/products")
    assert r.status_code == 200
    assert len(r.json()) == 10


def test_user_data_isolation(authed_client, mock_llm_available, reset_stores):
    """Admin uploads a 1-product file; a different anonymous session still sees sample data."""
    csv_one = (b"product_id,product_name,category,unit_cost_egp,selling_price_egp\n"
               b"P999,AdminPhone,Smartphones,100,150")
    r = authed_client.post("/api/upload",
                           files={"files": ("products.csv", csv_one, "text/csv")})
    assert r.status_code == 200

    r_admin = authed_client.get("/api/products")
    assert len(r_admin.json()) == 1

    with TestClient(app) as anon:
        r_anon = anon.get("/api/products")
        assert len(r_anon.json()) == 10
