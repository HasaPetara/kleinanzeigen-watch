"""Konfiguration laden und Such-URLs bauen.

Die URL wird aus den Feldern gebaut, damit man nur Werte aendern muss und
keine URL-Bastelei noetig ist. Das laesst sich alles in config.toml steuern.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

BASE_URL = "https://www.kleinanzeigen.de"


class ConfigError(Exception):
    """Konfiguration ist unbrauchbar."""


@dataclass(frozen=True)
class Telegram:
    chat_id: str = ""
    token_env: str = "TG_BOT_TOKEN"
    token: str = ""
    alert_after_failures: int = 3

    def resolve_token(self) -> str:
        if self.token:
            return self.token
        return os.environ.get(self.token_env, "").strip()


@dataclass(frozen=True)
class Search:
    name: str
    keyword: str
    zip: str = ""
    radius_km: int = 0
    price_min: int | None = None
    price_max: int | None = None
    only_offers: bool = True
    enabled: bool = True
    require: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    max_per_run: int = 10
    max_age_hours: int = 0
    notify_price_drop: bool = True

    def url(self) -> str:
        """Baut die Such-URL.

        Reihenfolge der Segmente ist von Kleinanzeigen vorgegeben:
        /s-sortierung:neueste/{plz}/{anzeige:angebote}/preis:min:max/{keyword}/k0r{radius}

        Das 'l1202' aus der Original-URL wird bewusst weggelassen: es aendert
        die Treffermenge nicht, zerstoert aber die Sortierung nach Datum.
        """
        parts = [BASE_URL, "s-sortierung:neueste"]
        if self.zip:
            parts.append(str(self.zip))
        if self.only_offers:
            parts.append("anzeige:angebote")
        if self.price_min is not None or self.price_max is not None:
            lo = "" if self.price_min is None else str(self.price_min)
            hi = "" if self.price_max is None else str(self.price_max)
            parts.append(f"preis:{lo}:{hi}")
        parts.append(slugify(self.keyword))
        parts.append(f"k0r{self.radius_km}" if self.radius_km else "k0")
        return "/".join(parts)


@dataclass(frozen=True)
class AppConfig:
    searches: list[Search]
    telegram: Telegram
    state_path: Path
    retention_days: int


def slugify(keyword: str) -> str:
    """Suchbegriff URL-tauglich machen (Leerzeichen -> Bindestrich)."""
    cleaned = " ".join(keyword.split()).lower().replace(" ", "-")
    return quote(cleaned, safe="-")


def load(path: str | Path) -> AppConfig:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Konfigurationsdatei nicht gefunden: {path}")

    # BOM-tolerant lesen: Editoren unter Windows schreiben gern eins davor.
    raw_bytes = path.read_bytes()
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        raw_bytes = raw_bytes[3:]
    try:
        raw = tomllib.loads(raw_bytes.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ConfigError(f"TOML-Fehler in {path.name}: {exc}") from exc

    searches: list[Search] = []
    for index, entry in enumerate(raw.get("searches", []), start=1):
        if not isinstance(entry, dict):
            raise ConfigError(f"[[searches]] Nr. {index} ist kein Tabellenblock")
        if not entry.get("keyword"):
            raise ConfigError(f"Suchauftrag Nr. {index}: 'keyword' fehlt")
        name = entry.get("name") or entry["keyword"]
        try:
            searches.append(
                Search(
                    name=str(name),
                    keyword=str(entry["keyword"]),
                    zip=str(entry.get("zip", "")),
                    radius_km=int(entry.get("radius_km", 0) or 0),
                    price_min=_opt_int(entry.get("price_min")),
                    price_max=_opt_int(entry.get("price_max")),
                    only_offers=bool(entry.get("only_offers", True)),
                    enabled=bool(entry.get("enabled", True)),
                    require=[str(p) for p in entry.get("require", [])],
                    exclude=[str(p) for p in entry.get("exclude", [])],
                    max_per_run=int(entry.get("max_per_run", 10)),
                    max_age_hours=int(entry.get("max_age_hours", 0) or 0),
                    notify_price_drop=bool(entry.get("notify_price_drop", True)),
                )
            )
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"Suchauftrag '{name}': {exc}") from exc

    if not searches:
        raise ConfigError("Kein [[searches]]-Block in der Konfiguration")

    names = [s.name for s in searches]
    if len(set(names)) != len(names):
        raise ConfigError("Suchauftraege brauchen eindeutige 'name'-Werte")

    tg_raw = raw.get("telegram", {})
    # chat_id darf auch aus der Umgebung kommen (z. B. GitHub-Secret TG_CHAT_ID),
    # damit sie nicht im oeffentlichen Repo steht.
    chat_id = (os.environ.get("TG_CHAT_ID") or str(tg_raw.get("chat_id", "") or "")).strip()
    telegram = Telegram(
        chat_id=chat_id,
        token_env=str(tg_raw.get("token_env", "TG_BOT_TOKEN") or "TG_BOT_TOKEN"),
        token=str(tg_raw.get("token", "") or ""),
        alert_after_failures=int(tg_raw.get("alert_after_failures", 3) or 3),
    )

    state_raw = raw.get("state", {})
    state_path = Path(str(state_raw.get("path", "state.json") or "state.json"))
    if not state_path.is_absolute():
        state_path = path.parent / state_path

    return AppConfig(
        searches=searches,
        telegram=telegram,
        state_path=state_path,
        retention_days=int(state_raw.get("retention_days", 30) or 30),
    )


def _opt_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
