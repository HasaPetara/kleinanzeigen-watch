"""Telegram-Versand ueber die Bot-API (sendMessage)."""

from __future__ import annotations

import html
import json
import urllib.error
import urllib.request

from .parse import Listing

API = "https://api.telegram.org/bot{token}/{method}"
MAX_LEN = 4000


class NotifyError(Exception):
    """Nachricht konnte nicht zugestellt werden."""


def _post(token: str, method: str, payload: dict, timeout: int = 20) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        API.format(token=token, method=method),
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        raise NotifyError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise NotifyError(f"Netzwerkfehler: {exc}") from exc

    if not result.get("ok"):
        raise NotifyError(f"API-Fehler: {result.get('description', result)}")
    return result


def send_text(
    token: str,
    chat_id: str,
    text: str,
    *,
    button_url: str | None = None,
    button_text: str = "Anzeige oeffnen",
    silent: bool = False,
) -> None:
    payload: dict = {
        "chat_id": chat_id,
        "text": text[:MAX_LEN],
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "disable_notification": silent,
    }
    if button_url:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": button_text, "url": button_url}]]
        }
    _post(token, "sendMessage", payload)


def format_listing(listing: Listing, search_name: str, *, price_drop: int | None = None) -> str:
    def esc(value: str) -> str:
        return html.escape(value, quote=False)

    money = esc(listing.price_text) if listing.price_text else "Preis n/a"
    where = esc(listing.location)
    if listing.distance_km is not None:
        where += f" · ca. {listing.distance_km:.0f} km"

    lines: list[str] = []
    if price_drop is not None and listing.price_value is not None:
        lines.append(f"📉 <b>Preis gefallen</b> · {esc(search_name)}")
    else:
        lines.append(f"🔔 <b>Neu</b> · {esc(search_name)}")

    lines.append("")
    lines.append(f"<b>{esc(listing.title)}</b>")
    lines.append(f"💰 {money}")
    lines.append(f"📍 {where}")
    if listing.posted:
        lines.append(f"🕒 {listing.posted.strftime('%d.%m.%Y')}")
    if listing.shipping:
        lines.append("📦 Versand möglich")

    if listing.description:
        preview = listing.description
        if len(preview) > 300:
            preview = preview[:297].rstrip() + "…"
        lines.append("")
        lines.append(f"<i>{esc(preview)}</i>")

    lines.append("")
    lines.append(f'<a href="{html.escape(listing.url, quote=True)}">Anzeige öffnen</a>')
    return "\n".join(lines)
