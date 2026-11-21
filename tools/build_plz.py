"""Baut data/plz_de.csv.gz aus den GeoNames-Postleitzahlendaten.

Aufruf:  python tools/build_plz.py
Quelle:  https://download.geonames.org/export/zip/DE.zip  (CC BY 4.0)
"""

from __future__ import annotations

import gzip
import io
import sys
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

URL = "https://download.geonames.org/export/zip/DE.zip"
OUT = Path(__file__).resolve().parents[1] / "data" / "plz_de.csv.gz"


def main() -> int:
    print(f"lade {URL} …", flush=True)
    request = urllib.request.Request(URL, headers={"User-Agent": "kleinanzeigen-watch/0.1"})
    raw = urllib.request.urlopen(request, timeout=120).read()

    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        lines = archive.read("DE.txt").decode("utf-8").splitlines()

    points: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for line in lines:
        fields = line.split("\t")
        if len(fields) < 11:
            continue
        postal_code = fields[1].strip()
        try:
            lat, lon = float(fields[9]), float(fields[10])
        except ValueError:
            continue
        if 47.0 <= lat <= 55.5 and 5.5 <= lon <= 15.5:  # nur Deutschland
            points[postal_code].append((lat, lon))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8", newline="\n") as fh:
        fh.write("# plz,lat,lon – Quelle: GeoNames (CC BY 4.0)\n")
        for postal_code in sorted(points):
            values = points[postal_code]
            lat = sum(v[0] for v in values) / len(values)
            lon = sum(v[1] for v in values) / len(values)
            fh.write(f"{postal_code},{lat:.5f},{lon:.5f}\n")

    print(f"{len(points)} Postleitzahlen -> {OUT} ({OUT.stat().st_size} Bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
