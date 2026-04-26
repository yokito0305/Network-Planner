"""FSR Lookup Service — Frame Success Rate table query.

Loads the pre-computed FSR table from
  data/fsr_tables.json   (generated from ref/thesis-wifi7/result/FSR_SNR/ CSVs)

on first use (lazy singleton per Python process).  Queries are O(1) index
lookups on in-memory float arrays.

Public API
----------
fsr_for_snr(band: BandId, width_mhz: int, mcs: int, snr_db: float) -> float
    Returns the frame success rate in [0.0, 1.0].
    Returns 0.0 for SNR below the table minimum (-5 dB).
    Returns 1.0 for SNR above the table maximum (55 dB).

all_mcs_fsr(band: BandId, width_mhz: int, snr_db: float) -> list[float]
    Returns FSR for MCS 0-13 at the given SNR (14-element list).

fsr_curve(band: BandId, width_mhz: int, mcs: int) -> list[tuple[float, float]]
    Returns the full (snr_db, fsr) curve for the given band/width/MCS.
    601 points: SNR = -5.0 to 55.0 in 0.1 dB steps.

available_keys() -> list[tuple[BandId, int]]
    Returns all valid (band, width_mhz) combinations loaded from the JSON.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from models.enums import BandId

# Constants
_SNR_MIN   = -5.0
_SNR_MAX   = 55.0
_SNR_STEP  = 0.1
_N_POINTS  = 601   # (55 - (-5)) / 0.1 + 1
_N_MCS     = 14    # MCS 0-13

# Map JSON directory key -> (BandId, width_mhz)
_DIR_TO_KEY: dict[str, tuple[BandId, int]] = {
    "2p4G-20band": (BandId.BAND_2G4, 20),
    "2p4G-40band": (BandId.BAND_2G4, 40),
    "5G-80band":   (BandId.BAND_5G,  80),
    "6G-160band":  (BandId.BAND_6G,  160),
}

# Reverse: (BandId, width) -> JSON key
_BAND_DIR: dict[tuple[BandId, int], str] = {v: k for k, v in _DIR_TO_KEY.items()}

# Fallback width per band (used when device reports None or unmapped width)
_DEFAULT_WIDTH: dict[BandId, int] = {
    BandId.BAND_2G4: 20,
    BandId.BAND_5G:  80,
    BandId.BAND_6G:  160,
}

# Internal table storage
# _TABLE[(band, width)][mcs] -> list[float] of length _N_POINTS
_TABLE: dict[tuple[BandId, int], list[list[float]]] | None = None


def _data_path() -> Path:
    """Resolve path to data/fsr_tables.json.

    Development: services/fsr_lookup.py -> repo_root/data/fsr_tables.json
    PyInstaller frozen: sys._MEIPASS/data/fsr_tables.json
      (--add-data "data/fsr_tables.json;data" puts the file into _MEIPASS/data/)
    """
    if getattr(sys, "frozen", False):
        # Frozen (PyInstaller): _MEIPASS is the _internal/ directory
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        # Development: this file is in services/, parent[1] is repo root
        base = Path(__file__).resolve().parents[1]
    return base / "data" / "fsr_tables.json"


def _load_table() -> dict[tuple[BandId, int], list[list[float]]]:
    path = _data_path()
    if not path.exists():
        raise FileNotFoundError(
            f"FSR table not found: {path}\n"
            "Run the extraction script to regenerate data/fsr_tables.json."
        )
    with path.open(encoding="utf-8") as f:
        raw: dict[str, list[list[float]]] = json.load(f)

    table: dict[tuple[BandId, int], list[list[float]]] = {}
    for dir_name, mcs_table in raw.items():
        key = _DIR_TO_KEY.get(dir_name)
        if key is None:
            continue
        table[key] = mcs_table
    return table


def _get_table() -> dict[tuple[BandId, int], list[list[float]]]:
    global _TABLE
    if _TABLE is None:
        _TABLE = _load_table()
    return _TABLE


def _resolve_key(band: BandId, width_mhz: int | None) -> tuple[BandId, int]:
    """Return the closest valid (band, width) key."""
    if width_mhz is None:
        width_mhz = _DEFAULT_WIDTH.get(band, 20)
    key = (band, width_mhz)
    if key in _BAND_DIR:
        return key
    w = _DEFAULT_WIDTH.get(band, 20)
    return (band, w)


def fsr_for_snr(band: BandId, width_mhz: int | None, mcs: int, snr_db: float) -> float:
    """Return FSR in [0.0, 1.0] for the given band/width/MCS at snr_db."""
    if snr_db <= _SNR_MIN:
        return 0.0
    if snr_db >= _SNR_MAX:
        return 1.0
    key = _resolve_key(band, width_mhz)
    tbl = _get_table()
    if key not in tbl:
        return 0.0
    if not (0 <= mcs < _N_MCS):
        return 0.0
    idx = round((snr_db - _SNR_MIN) / _SNR_STEP)
    idx = max(0, min(_N_POINTS - 1, idx))
    return tbl[key][mcs][idx]


def all_mcs_fsr(band: BandId, width_mhz: int | None, snr_db: float) -> list[float]:
    """Return FSR for MCS 0-13 at snr_db (14-element list)."""
    return [fsr_for_snr(band, width_mhz, mcs, snr_db) for mcs in range(_N_MCS)]


def fsr_curve(band: BandId, width_mhz: int | None, mcs: int) -> list[tuple[float, float]]:
    """Return full (snr_db, fsr) curve -- 601 points, SNR -5.0 to 55.0."""
    key = _resolve_key(band, width_mhz)
    tbl = _get_table()
    if key not in tbl or not (0 <= mcs < _N_MCS):
        return []
    col = tbl[key][mcs]
    return [(_SNR_MIN + i * _SNR_STEP, col[i]) for i in range(_N_POINTS)]


def available_keys() -> list[tuple[BandId, int]]:
    """Return all valid (band, width_mhz) combinations loaded from the JSON."""
    tbl = _get_table()
    return list(tbl.keys())
