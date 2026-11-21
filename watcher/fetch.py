"""HTTP-Abruf mit realistischen Headern, Retry und Bot-Schutz-Erkennung."""

from __future__ import annotations

import gzip
import random
import time
import urllib.error
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
    "Accept-Encoding": "gzip",
    "Connection": "close",
    "Upgrade-Insecure-Requests": "1",
}


class FetchError(Exception):
    """Abruf fehlgeschlagen (Netz, Timeout, unerwarteter Status)."""


class Blocked(FetchError):
    """Der Server hat den Abruf erkennbar abgelehnt (Bot-Schutz)."""


def decode_page(raw: bytes) -> str:
    """Kleinanzeigen liefert cp1252-Bytes, obwohl UTF-8 deklariert ist."""
    for encoding in ("utf-8", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def fetch_html(
    url: str,
    *,
    timeout: int = 40,
    attempts: int = 3,
    backoff: float = 2.5,
    jitter: float = 0.0,
    logger=print,
) -> str:
    """Holt eine Seite als Text.

    - wiederholt bei Netzwerkfehlern und 5xx (mit wachsender Pause)
    - bricht bei 403/429 sofort ab, statt den Server zu bearbeiten
    """
    last_error: FetchError | None = None

    for attempt in range(1, attempts + 1):
        if jitter:
            time.sleep(random.uniform(0, jitter))
        request = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                if response.headers.get("Content-Encoding", "").lower() == "gzip":
                    raw = gzip.decompress(raw)
                return decode_page(raw)
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                raise Blocked(f"HTTP {exc.code} – vermutlich Bot-Schutz") from exc
            last_error = FetchError(f"HTTP {exc.code}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = FetchError(f"{type(exc).__name__}: {exc}")

        if attempt < attempts:
            pause = backoff * attempt
            logger(f"  Versuch {attempt} fehlgeschlagen ({last_error}) – warte {pause:.0f}s")
            time.sleep(pause)

    raise last_error or FetchError("unbekannter Fehler")
