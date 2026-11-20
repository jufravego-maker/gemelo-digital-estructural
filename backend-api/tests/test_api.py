"""Pruebas de la API en modo demo (sin base de datos)."""
import os
import sys
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
os.environ.pop("GEMINI_API_KEY", None)
os.environ["WS_INTERVAL_S"] = "0.1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from stiffness import classify, stiffness_from_frequency  # noqa: E402

client = TestClient(app)


def test_health_demo_mode():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["mode"] == "demo"


def test_four_buildings_one_reference():
    fc = client.get("/api/buildings").json()
    props = {f["properties"]["building_id"]: f["properties"] for f in fc["features"]}
    assert set(props) == {"EDIF-01", "EDIF-02", "EDIF-03", "EDIF-04"}
    assert props["EDIF-04"]["is_monitored"] is False
    assert props["EDIF-04"]["status"] == "referencia"
    assert props["EDIF-04"]["sensor_count"] == 0
    assert all(props[b]["sensor_count"] == 4 for b in ("EDIF-01", "EDIF-02", "EDIF-03"))


def test_demo_scenario_statuses():
    props = {f["properties"]["building_id"]: f["properties"]
             for f in client.get("/api/buildings").json()["features"]}
    assert props["EDIF-03"]["status"] == "critico"
    assert props["EDIF-02"]["status"] == "alerta"
    assert props["EDIF-01"]["status"] == "optimo"


def test_building_detail_links_cobie():
    d = client.get("/api/buildings/EDIF-04").json()
    assert d["sensors"] == []
    assert len(d["components"]) == 3


def test_element_detail_joins_three_keys():
    d = client.get("/api/elements/1hQ5Rk9vT2mXa8LpE3C001").json()
    assert d["component"]["building_id"] == "EDIF-03"
    assert d["sensor"]["sensor_id"] == "S-E03-01"
    assert any(a["name"] == "ResistenciaConcreto" for a in d["attributes"])


def test_element_not_found():
    assert client.get("/api/elements/XXXXXXXXXXXXXXXXXXXXXX").status_code == 404


def test_series_and_csv():
    d = client.get("/api/stiffness", params={"building_id": "EDIF-01", "hours": 24}).json()
    assert len(d["series"]) == 4
    assert all(len(s["points"]) > 10 for s in d["series"])
    r = client.get("/api/stiffness/export.csv", params={"sensor_id": "S-E01-01", "hours": 24})
    assert r.status_code == 200
    assert r.text.splitlines()[0].startswith("time_utc,building_id,sensor_id")


def test_ingest_frequency_computes_k():
    # 3.12 Hz con 135 t ≈ 51 900 kN/m (cerca del diseño, 52 000 kN/m)
    r = client.post("/api/telemetry", json={"sensor_id": "S-E01-01", "frequency_hz": 3.12})
    assert r.status_code == 201
    body = r.json()
    assert abs(body["k_kn_m"] - round(stiffness_from_frequency(3.12, 135), 1)) < 0.2
    assert body["status"] == "optimo"


def test_ingest_requires_measure():
    assert client.post("/api/telemetry", json={"sensor_id": "S-E01-01"}).status_code == 422
    assert client.post("/api/telemetry", json={"sensor_id": "NOPE", "k_kn_m": 1}).status_code == 404


def test_ai_summary_rules_fallback():
    d = client.post("/api/ai/summary", json={}).json()
    assert d["source"] == "reglas"
    assert "EDIF-03" in d["text"]


def test_classify_thresholds():
    assert classify(-1) == "optimo"
    assert classify(-6) == "alerta"
    assert classify(-20) == "critico"
    assert classify(None) == "sin_dato"


def test_websocket_snapshot():
    with client.websocket_connect("/ws/stiffness") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "snapshot"
    assert msg["buildings"]["EDIF-04"] == "referencia"
