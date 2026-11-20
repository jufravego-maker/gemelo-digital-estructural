"""Procesamiento de señales IoT y cálculo de rigidez estructural k.

Modelo de un grado de libertad equivalente del elemento/modo:
    k = m · (2·π·f)²            [N/m]  ->  /1000  [kN/m]
    Δk = (k - k_diseño) / k_diseño · 100   [%]

donde f es la frecuencia natural identificada a partir de la señal de aceleración (pico del
espectro de Fourier) y m la masa modal participante (tabla maestra, columna modal_mass_t).

Uso como librería:
    from stiffness_calculator import dominant_frequency, stiffness_from_frequency
Uso por línea de comandos (archivo CSV con columnas time_s, accel):
    python etl-scripts/stiffness_calculator.py senal.csv --sensor S-E01-01
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys

import numpy as np

from cde_paths import MASTER_CSV

DK_WARN_PCT = float(os.getenv("DK_WARN_PCT", "-5"))
DK_CRIT_PCT = float(os.getenv("DK_CRIT_PCT", "-15"))


def dominant_frequency(accel: np.ndarray, fs_hz: float, fmin: float = 0.5, fmax: float = 25.0) -> float:
    """Frecuencia dominante [Hz] de una señal de aceleración (FFT con ventana de Hann
    e interpolación parabólica del pico)."""
    x = np.asarray(accel, dtype=float)
    x = x - x.mean()
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freqs = np.fft.rfftfreq(len(x), d=1.0 / fs_hz)
    band = (freqs >= fmin) & (freqs <= fmax)
    if not band.any():
        raise ValueError("La banda de búsqueda no contiene frecuencias; revise fs y la duración")
    idx = np.flatnonzero(band)[np.argmax(spec[band])]
    if 0 < idx < len(spec) - 1:
        a, b, c = spec[idx - 1], spec[idx], spec[idx + 1]
        denom = a - 2 * b + c
        offset = 0.5 * (a - c) / denom if denom else 0.0
        return float(freqs[idx] + offset * (freqs[1] - freqs[0]))
    return float(freqs[idx])


def stiffness_from_frequency(f_hz: float, modal_mass_t: float) -> float:
    """Rigidez [kN/m] a partir de frecuencia [Hz] y masa modal [t]."""
    return modal_mass_t * 1000.0 * (2 * math.pi * f_hz) ** 2 / 1000.0


def frequency_from_stiffness(k_kn_m: float, modal_mass_t: float) -> float:
    return math.sqrt(k_kn_m * 1000.0 / (modal_mass_t * 1000.0)) / (2 * math.pi)


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


def load_sensor(sensor_id: str) -> dict:
    with open(MASTER_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["sensor_id"] == sensor_id:
                return row
    raise SystemExit(f"Sensor {sensor_id} no está en la tabla maestra")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("signal_csv", help="CSV con columnas time_s, accel")
    ap.add_argument("--sensor", required=True, help="sensor_id de la tabla maestra")
    args = ap.parse_args()

    sensor = load_sensor(args.sensor)
    data = np.genfromtxt(args.signal_csv, delimiter=",", names=True)
    t, a = data["time_s"], data["accel"]
    fs = 1.0 / np.median(np.diff(t))
    f = dominant_frequency(a, fs)
    k = stiffness_from_frequency(f, float(sensor["modal_mass_t"]))
    dk = delta_k_pct(k, float(sensor["k_design_kn_m"]))
    print(f"Sensor {args.sensor} ({sensor['building_id']} / {sensor['ifc_global_id']})")
    print(f"  fs = {fs:.1f} Hz | f = {f:.3f} Hz | k = {k:,.0f} kN/m | Δk = {dk:+.2f} % -> {classify(dk)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
