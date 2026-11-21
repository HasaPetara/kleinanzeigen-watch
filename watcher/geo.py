"""Entfernung zwischen Postleitzahlen (Luftlinie).

Kleinanzeigen wendet den Umkreis nur im Browser an, die ausgelieferte
HTML-Seite ignoriert 'r200' komplett. Deshalb rechnen wir selbst:
data/plz_de.csv.gz enthaelt die PLZ-Mittelpunkte (Quelle: GeoNames).
"""

from __future__ import annotations

import gzip
import math
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "plz_de.csv.gz"
EARTH_RADIUS_KM = 6371.0

_TABLE: dict[str, tuple[float, float]] | None = None


def _table() -> dict[str, tuple[float, float]]:
    global _TABLE
    if _TABLE is None:
        table: dict[str, tuple[float, float]] = {}
        with gzip.open(DATA_FILE, "rt", encoding="utf-8") as fh:
            for line in fh:
                if not line or line.startswith("#"):
                    continue
                parts = line.strip().split(",")
                if len(parts) != 3:
                    continue
                try:
                    table[parts[0]] = (float(parts[1]), float(parts[2]))
                except ValueError:
                    continue
        _TABLE = table
    return _TABLE


def coords(postal_code: str | None) -> tuple[float, float] | None:
    if not postal_code:
        return None
    return _table().get(str(postal_code).strip()[:5])


def distance_km(from_plz: str | None, to_plz: str | None) -> float | None:
    """Luftlinie in km, oder None wenn eine PLZ unbekannt ist."""
    start, end = coords(from_plz), coords(to_plz)
    if start is None or end is None:
        return None

    lat1, lon1 = map(math.radians, start)
    lat2, lon2 = map(math.radians, end)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a)), 1)
