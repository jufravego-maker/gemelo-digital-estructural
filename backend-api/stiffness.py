"""Indicadores de rigidez estructural y semáforo de estado."""
from __future__ import annotations

import math
import os

DK_WARN_PCT = float(os.getenv("DK_WARN_PCT", "-5"))
DK_CRIT_PCT = float(os.getenv("DK_CRIT_PCT", "-15"))

# Orden de severidad para agregar el estado de un edificio
SEVERITY = {"sin_dato": 0, "optimo": 1, "alerta": 2, "critico": 3}


def delta_k_pct(k: float, k_design: float) -> float:
    return (k - k_design) / k_design * 100.0


def classify(dk_pct: float | None) -> str:
    if dk_pct is None:
        return "sin_dato"
    if dk_pct <= DK_CRIT_PCT:
        return "critico"
    if dk_pct <= DK_WARN_PCT:
        return "alerta"
    return "optimo"


def stiffness_from_frequency(f_hz: float, modal_mass_t: float) -> float:
    """k [kN/m] = m [kg] · (2πf)² / 1000."""
    return modal_mass_t * 1000.0 * (2 * math.pi * f_hz) ** 2 / 1000.0


def worst(statuses: list[str]) -> str:
    return max(statuses, key=lambda s: SEVERITY.get(s, 0)) if statuses else "sin_dato"
