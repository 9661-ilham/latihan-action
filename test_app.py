"""Uji otomatis aq-service. Dijalankan oleh GitHub Actions sebelum image dibangun."""
from fastapi.testclient import TestClient

import app as service

client = TestClient(service.app)


def setup_function():
    service.READINGS.clear()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_post_and_list_reading():
    r = client.post("/readings", json={"sensor_id": "aq-001", "pm25": 40.0})
    assert r.status_code == 201
    data = client.get("/readings").json()
    assert len(data) == 1 and data[0]["sensor_id"] == "aq-001"


def test_negative_pm25_rejected():
    r = client.post("/readings", json={"sensor_id": "aq-001", "pm25": -5})
    assert r.status_code == 422


def test_alert_above_threshold():
    client.post("/readings", json={"sensor_id": "aq-001", "pm25": service.ALERT_THRESHOLD + 10})
    client.post("/readings", json={"sensor_id": "aq-002", "pm25": service.ALERT_THRESHOLD - 10})
    alerts = client.get("/alerts").json()["alerts"]
    assert [a["sensor_id"] for a in alerts] == ["aq-001"]
