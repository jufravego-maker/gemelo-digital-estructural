"""Asistente de resúmenes ejecutivos.

Si existe GEMINI_API_KEY usa la Gemini API; si no (o si falla), genera un resumen por reglas
para que el dashboard siempre tenga una respuesta.
"""
from __future__ import annotations

import json
import os

import httpx

from stiffness import DK_CRIT_PCT, DK_WARN_PCT

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

STATUS_ES = {"optimo": "óptimo", "alerta": "alerta", "critico": "crítico",
             "referencia": "referencia", "sin_dato": "sin dato"}


def provider() -> str:
    return "gemini" if os.getenv("GEMINI_API_KEY") else "reglas"


async def summarize(buildings: list[dict], sensors: list[dict], cobie: dict[str, list[dict]]) -> dict:
    if os.getenv("GEMINI_API_KEY"):
        try:
            return {"source": "gemini", "model": GEMINI_MODEL,
                    "text": await _gemini(buildings, sensors, cobie)}
        except Exception as exc:  # noqa: BLE001 — se degrada al resumen por reglas
            fallback = _rules(buildings, sensors)
            fallback["warning"] = f"Gemini no disponible ({type(exc).__name__}); resumen por reglas."
            return fallback
    return _rules(buildings, sensors)


def _compact_sensors(sensors):
    keys = ("sensor_id", "building_id", "element_name", "ifc_class", "level", "k_design_kn_m",
            "k_kn_m", "delta_k_pct", "status")
    return [{k: s.get(k) for k in keys} for s in sensors]


async def _gemini(buildings, sensors, cobie) -> str:
    prompt = (
        "Eres un ingeniero estructural que supervisa un gemelo digital (BIM + GIS + IoT). "
        "Redacta en español un resumen ejecutivo breve (máximo 200 palabras) del estado de rigidez "
        "estructural y, si corresponde, alertas de mantenimiento predictivo priorizadas. "
        f"Criterios: Δk ≤ {DK_WARN_PCT}% es alerta y Δk ≤ {DK_CRIT_PCT}% es crítico. "
        "La edificación con status 'referencia' no tiene sensores y sirve de línea base. "
        "No inventes datos que no estén abajo.\n\n"
        f"EDIFICACIONES:\n{json.dumps(buildings, ensure_ascii=False, default=str)}\n\n"
        f"SENSORES:\n{json.dumps(_compact_sensors(sensors), ensure_ascii=False)}\n\n"
        f"COBIE DE ELEMENTOS EN ALERTA:\n{json.dumps(cobie, ensure_ascii=False)}"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            GEMINI_URL.format(model=GEMINI_MODEL),
            headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
            json={"contents": [{"parts": [{"text": prompt}]}]},
        )
        r.raise_for_status()
        data = r.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def _rules(buildings, sensors) -> dict:
    lines = []
    monitored = [b for b in buildings if b.get("is_monitored")]
    lines.append(f"Estado general: {len(monitored)} edificaciones monitoreadas y "
                 f"{len(buildings) - len(monitored)} de referencia.")
    for b in buildings:
        st = STATUS_ES.get(b["status"], b["status"])
        dk = b.get("worst_delta_k_pct")
        extra = f" (peor Δk {dk:+.1f} %)" if dk is not None else ""
        lines.append(f"• {b['building_id']} – {b.get('name', '')}: {st}{extra}.")
    crit = sorted([s for s in sensors if s["status"] == "critico"], key=lambda s: s["delta_k_pct"])
    warn = sorted([s for s in sensors if s["status"] == "alerta"], key=lambda s: s["delta_k_pct"])
    if crit:
        lines.append("Acciones prioritarias:")
        lines += [f"  – {s['element_name']} ({s['building_id']}, {s['ifc_class']}, nivel {s['level']}): "
                  f"Δk {s['delta_k_pct']:+.1f} %. Inspección estructural detallada inmediata."
                  for s in crit]
    if warn:
        lines.append("Seguimiento:")
        lines += [f"  – {s['element_name']} ({s['building_id']}): Δk {s['delta_k_pct']:+.1f} %. "
                  "Aumentar frecuencia de lectura y programar inspección visual." for s in warn]
    if not crit and not warn:
        lines.append("Sin elementos en alerta: todos los sensores dentro del rango óptimo.")
    return {"source": "reglas", "text": "\n".join(lines)}
