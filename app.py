"""Layanan API kualitas udara — contoh praktikum SS-302 P5."""
import os
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel, Field

SERVICE_NAME = os.getenv("SERVICE_NAME", "aq-service")
# Ambang contoh untuk latihan; ganti sesuai kebutuhan layanan kelompok.
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "55.5"))

app = FastAPI(title="Layanan Kualitas Udara (contoh SS-302)")
READINGS: list["Reading"] = []  # disimpan di memori; hilang saat container dihapus


class Reading(BaseModel):
    sensor_id: str = Field(..., examples=["aq-001"])
    pm25: float = Field(..., ge=0, le=1000, description="PM2.5 dalam µg/m³")
    timestamp: datetime | None = None


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE_NAME}


@app.post("/readings", status_code=201)
def add_reading(reading: Reading):
    reading.timestamp = reading.timestamp or datetime.now(timezone.utc)
    READINGS.append(reading)
    return reading


@app.get("/readings")
def list_readings(sensor_id: str | None = None, limit: int = 50):
    data = [r for r in READINGS if sensor_id is None or r.sensor_id == sensor_id]
    return data[-limit:]


@app.get("/alerts")
def alerts():
    return {"threshold": ALERT_THRESHOLD,
            "alerts": [r for r in READINGS if r.pm25 > ALERT_THRESHOLD]}
