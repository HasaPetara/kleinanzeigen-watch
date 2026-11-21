"""HTML der Trefferliste in Anzeigen-Objekte umwandeln.

Die Liste ist serverseitig gerendert: pro Treffer ein
<article data-adid="..." data-href="...">. Titel und Textanfang stehen
zusaetzlich als JSON-LD im Block, das ist die zuverlaessigste Quelle.
"""

from __future__ import annotations

import html as html_mod
import json
import re
from dataclasses import dataclass
from datetime import date

BASE_URL = "https://www.kleinanzeigen.de"

_ARTICLE_RE = re.compile(r"<article\b([^>]*)>(.*?)</article>", re.S | re.I)
_LDJSON_RE = re.compile(r'application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I)
_PRICE_RE = re.compile(r'<p[^>]*class="[^"]*text-secondary[^"]*"[^>]*>(.*?)</p>', re.S | re.I)
_TITLE_RE = re.compile(r"<h3[^>]*>(.*?)</h3>", re.S | re.I)
_DESC_RE = re.compile(
    r'<p[^>]*class="[^"]*text-onSurfaceSubdued[^"]*"[^>]*>(.*?)</p>', re.S | re.I
)
_LOCATION_RE = re.compile(r"<span>\s*(\d{5})\s+([^<]+?)\s*</span>")
_DISTANCE_RE = re.compile(r"\(ca\.\s*([\d]+(?:[.,]\d+)?)\s*km\)")
_DATE_RE = re.compile(r"<span>\s*(\d{2})\.(\d{2})\.(\d{4})\s*</span>")
_TAGS_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class Listing:
    adid: str
    href: str
    title: str
    description: str
    price_text: str
    price_value: int | None
    zip_code: str
    city: str
    distance_km: float | None
    posted: date | None
    shipping: bool

    @property
    def url(self) -> str:
        return f"{BASE_URL}{self.href}" if self.href.startswith("/") else self.href

    @property
    def slug(self) -> str:
        return self.href.rsplit("/", 1)[-1]

    @property
    def haystack(self) -> str:
        """Text, gegen den require/exclude laufen (klein geschrieben)."""
        slug_words = re.sub(r"[-_]+", " ", self.href).replace("/s anzeige/", " ")
        return f"{self.title} {self.description} {slug_words}".lower()

    @property
    def location(self) -> str:
        if self.zip_code and self.city:
            return f"{self.zip_code} {self.city}"
        return self.city or self.zip_code or "?"


def clean(text: str) -> str:
    """Tags weg, Entities aufloesen, Leerraum normalisieren."""
    text = _TAGS_RE.sub(" ", text)
    text = html_mod.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def parse_price(text: str) -> tuple[str, int | None]:
    """Preisangabe in (Anzeigetext, Zahlenwert) zerlegen."""
    label = clean(text)
    if not label:
        return "", None
    lowered = label.lower()
    if "verschenken" in lowered:
        return label, 0
    match = re.search(r"([\d][\d.]{0,8})\s*€", label)
    if match:
        try:
            return label, int(match.group(1).replace(".", ""))
        except ValueError:
            return label, None
    return label, None


def _parse_date(block: str) -> date | None:
    match = _DATE_RE.search(block)
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _json_ld(block: str) -> dict:
    match = _LDJSON_RE.search(block)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def parse_listings(page: str) -> list[Listing]:
    """Alle Treffer einer Ergebnisseite extrahieren."""
    listings: list[Listing] = []

    for attrs, block in _ARTICLE_RE.findall(page):
        adid_match = re.search(r'data-adid="(\d+)"', attrs)
        href_match = re.search(r'data-href="([^"]+)"', attrs)
        if not adid_match or not href_match:
            continue
        adid = adid_match.group(1)
        href = html_mod.unescape(href_match.group(1))

        ld = _json_ld(block)
        title = clean(str(ld.get("title") or ""))
        if not title:
            title_match = _TITLE_RE.search(block)
            title = clean(title_match.group(1)) if title_match else ""

        description = clean(str(ld.get("description") or ""))
        if not description:
            desc_match = _DESC_RE.search(block)
            description = clean(desc_match.group(1)) if desc_match else ""

        price_match = _PRICE_RE.search(block)
        price_text, price_value = parse_price(price_match.group(1) if price_match else "")

        location_match = _LOCATION_RE.search(block)
        zip_code, city = ("", "")
        if location_match:
            zip_code, city = location_match.group(1), clean(location_match.group(2))

        distance_match = _DISTANCE_RE.search(block)
        distance_km = None
        if distance_match:
            try:
                distance_km = float(distance_match.group(1).replace(",", "."))
            except ValueError:
                distance_km = None

        listings.append(
            Listing(
                adid=adid,
                href=href,
                title=title or "(ohne Titel)",
                description=description,
                price_text=price_text,
                price_value=price_value,
                zip_code=zip_code,
                city=city,
                distance_km=distance_km,
                posted=_parse_date(block),
                shipping="data-dhl-promotion" in block,
            )
        )

    return listings
