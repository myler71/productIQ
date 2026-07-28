"""End-to-end FastAPI route tests."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_get_analytics(client):
    r = client.get("/api/analytics")
    assert r.status_code == 200
    data = r.json()
    assert data["kpis"]["revenue"] > 0


def test_get_products(client):
    r = client.get("/api/products")
    assert r.status_code == 200
    assert len(r.json()) == 10


def test_recommendations_returns_engine(client):
    r = client.get("/api/recommendations?lang=en")
    assert r.status_code == 200
    data = r.json()
    assert "engine" in data


def test_ceo_report_returns_engine(client):
    r = client.post("/api/ceo-report?lang=en")
    assert r.status_code == 200
    data = r.json()
    assert "engine" in data


def test_simulate_returns_engine(client):
    payload = {
        "product_id": "P001", "product_name": "Samsung Galaxy A56",
        "current_price": 5990, "change_type": "price decrease", "change_value": 10
    }
    r = client.post("/api/simulate", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "engine" in data


def test_board_meeting_returns_engine(client):
    r = client.post("/api/board-meeting", json={"product_id": "P001", "lang": "en"})
    assert r.status_code == 200
    data = r.json()
    assert "engine" in data
    assert len(data["transcript"]) == 4


def test_session_cookie_created(client):
    r = client.get("/api/analytics")
    assert "productiq_session" in client.cookies


def test_upload_validation(client):
    csv_bad = b"product_id,product_name,category,unit_cost_egp,selling_price_egp\nP001,Phone,Smartphones,100,-50"
    r = client.post("/api/upload", files={"files": ("products.csv", csv_bad, "text/csv")})
    assert r.status_code == 200
    data = r.json()
    assert data["files"][0]["rejected"] == 1


def test_recommendations_offline_badge(client_offline):
    r = client_offline.get("/api/recommendations?lang=en")
    assert r.status_code == 200
    assert r.json()["engine"] == "deterministic"
