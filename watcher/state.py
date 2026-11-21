"""Zustand: welche Anzeigen wurden schon gemeldet?

Bewusst eine simple JSON-Datei: klein, lesbar, ohne Datenbank.
Bei einem Wechsel auf Cloudflare/Workers wird das durch KV ersetzt.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class State:
    def __init__(self, path: Path, retention_days: int = 30) -> None:
        self.path = Path(path)
        self.retention_days = retention_days
        self.data: dict = {"version": 1, "searches": {}}

    def load(self) -> "State":
        if self.path.is_file():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8-sig"))
            except (json.JSONDecodeError, OSError):
                self.data = {"version": 1, "searches": {}}
        self.data.setdefault("version", 1)
        self.data.setdefault("searches", {})
        return self

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.prune()
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def search(self, name: str) -> dict:
        entry = self.data["searches"].setdefault(
            name,
            {"initialized": False, "failures": 0, "alerted": False, "seen": {}},
        )
        entry.setdefault("seen", {})
        entry.setdefault("failures", 0)
        entry.setdefault("alerted", False)
        return entry

    def is_seen(self, name: str, adid: str) -> bool:
        return adid in self.search(name)["seen"]

    def price_of(self, name: str, adid: str) -> int | None:
        record = self.search(name)["seen"].get(adid) or {}
        value = record.get("price")
        return value if isinstance(value, int) else None

    def mark(self, name: str, adid: str, price: int | None) -> None:
        self.search(name)["seen"][adid] = {"t": _now(), "price": price}

    def prune(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        for entry in self.data["searches"].values():
            seen = entry.get("seen", {})
            for adid, record in list(seen.items()):
                try:
                    seen_at = datetime.fromisoformat(str(record.get("t")))
                except (TypeError, ValueError):
                    seen_at = None
                if seen_at and seen_at < cutoff:
                    del seen[adid]
