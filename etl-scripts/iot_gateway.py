"""Pasarela IoT: simulador de sensores y puente MQTT -> API.

Subcomandos:
  simulate  Genera lecturas sintéticas de frecuencia para los sensores de la tabla maestra y
            las envía a la API (HTTP) o las publica en MQTT (--mqtt).
  bridge    Se suscribe al broker MQTT (Eclipse Mosquitto) y reenvía cada lectura a la API.

Tópico MQTT: gemelo/<building_id>/<sensor_id>/rigidez
Mensaje JSON: {"sensor_id": "...", "time": "ISO-8601", "frequency_hz": 3.18}  (o "k_kn_m")

Ejemplos:
    python etl-scripts/iot_gateway.py simulate --api http://localhost:8000 --interval 5
    python etl-scripts/iot_gateway.py simulate --mqtt localhost --interval 5
    python etl-scripts/iot_gateway.py bridge --mqtt localhost --api http://localhost:8000
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from datetime import datetime, timezone

import requests

from cde_paths import MASTER_CSV
from stiffness_calculator import frequency_from_stiffness

TOPIC = "gemelo/{building_id}/{sensor_id}/rigidez"


def load_sensors() -> list[dict]:
    with open(MASTER_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def simulate(args) -> None:
    sensors = load_sensors()
    client = None
    if args.mqtt:
        import paho.mqtt.client as mqtt
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="gemelo-simulador")
        client.connect(args.mqtt, args.port)
        client.loop_start()
    print(f"Simulando {len(sensors)} sensores cada {args.interval}s (Ctrl+C para detener)")
    while True:
        now = datetime.now(timezone.utc).isoformat()
        for s in sensors:
            k = float(s["k_design_kn_m"]) * (1 + random.gauss(-0.01, 0.008))
            f = frequency_from_stiffness(k, float(s["modal_mass_t"]))
            msg = {"sensor_id": s["sensor_id"], "time": now, "frequency_hz": round(f, 4)}
            if client:
                client.publish(TOPIC.format(**s), json.dumps(msg), qos=1)
            else:
                r = requests.post(f"{args.api}/api/telemetry", json=msg, timeout=10)
                r.raise_for_status()
        print(f"{now}: {len(sensors)} lecturas enviadas")
        time.sleep(args.interval)


def bridge(args) -> None:
    import paho.mqtt.client as mqtt

    def on_connect(client, userdata, flags, reason_code, properties):
        client.subscribe("gemelo/+/+/rigidez", qos=1)
        print(f"Conectado a {args.mqtt}:{args.port}, suscrito a gemelo/+/+/rigidez")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload)
            r = requests.post(f"{args.api}/api/telemetry", json=payload, timeout=10)
            r.raise_for_status()
        except Exception as exc:  # noqa: BLE001 — el puente no debe detenerse por una lectura
            print(f"[ERROR] {msg.topic}: {exc}")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="gemelo-bridge")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.mqtt, args.port)
    client.loop_forever()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("simulate", "bridge"):
        p = sub.add_parser(name)
        p.add_argument("--api", default="http://localhost:8000")
        p.add_argument("--mqtt", help="Host del broker MQTT")
        p.add_argument("--port", type=int, default=1883)
        if name == "simulate":
            p.add_argument("--interval", type=float, default=5.0)
    args = ap.parse_args()
    if args.cmd == "bridge" and not args.mqtt:
        ap.error("bridge requiere --mqtt")
    try:
        (simulate if args.cmd == "simulate" else bridge)(args)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
