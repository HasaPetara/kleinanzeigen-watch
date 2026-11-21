"""Kommandozeile: ein Lauf = einmal alle Suchauftraege pruefen.

Beispiele:
    python -m watcher --dry-run -v     # nur anzeigen, nichts senden/speichern
    python -m watcher --seed           # Baseline setzen (erster Lauf)
    python -m watcher                  # normaler Lauf (fuer cron)
    python -m watcher --test-telegram  # Bot-Konfiguration pruefen
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from . import config as config_module
from . import geo
from .fetch import Blocked, FetchError, fetch_html
from .filters import RuleError, compile_rules, evaluate
from .notify import NotifyError, format_listing, send_text
from .parse import Listing, parse_listings
from .state import State

OK = "OK"
BAD = "--"


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kleinanzeigen-watch",
        description="Kleinanzeigen-Suchen beobachten und per Telegram melden.",
    )
    parser.add_argument("-c", "--config", default="config.toml", help="Pfad zur config.toml")
    parser.add_argument("--state", default=None, help="State-Datei ueberschreiben")
    parser.add_argument("--dry-run", action="store_true", help="nichts senden, nichts speichern")
    parser.add_argument("--seed", action="store_true", help="nur Baseline setzen, keine Nachrichten")
    parser.add_argument("--test-telegram", action="store_true", help="Testnachricht senden")
    parser.add_argument("--limit", type=int, default=None, help="max. Nachrichten pro Suche (Test)")
    parser.add_argument("-v", "--verbose", action="store_true", help="auch aussortierte Treffer zeigen")
    return parser


def _setup_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _setup_console()
    args = build_parser().parse_args(argv)

    try:
        cfg = config_module.load(args.config)
    except config_module.ConfigError as exc:
        print(f"Konfigurationsfehler: {exc}", file=sys.stderr)
        return 1

    state_path = Path(args.state) if args.state else cfg.state_path
    state = State(state_path, cfg.retention_days).load()

    token = cfg.telegram.resolve_token()
    if args.test_telegram:
        if not token or not cfg.telegram.chat_id:
            print("Token (Umgebungsvariable) und chat_id muessen gesetzt sein.", file=sys.stderr)
            return 1
        try:
            send_text(token, cfg.telegram.chat_id, "✅ kleinanzeigen-watch: Testnachricht")
        except NotifyError as exc:
            print(f"Telegram-Fehler: {exc}", file=sys.stderr)
            return 1
        print("Testnachricht verschickt.")
        return 0

    can_send = bool(token and cfg.telegram.chat_id) and not args.dry_run
    if not args.dry_run and not can_send:
        log("Hinweis: kein Token/chat_id gesetzt – es wird nur geloggt, nicht gesendet.")

    now = datetime.now()
    failures_total = 0
    handled_total = 0

    for search in cfg.searches:
        if not search.enabled:
            log(f"– {search.name}: deaktiviert")
            continue

        limit = args.limit if args.limit is not None else search.max_per_run
        entry = state.search(search.name)
        url = search.url()
        log(f"> {search.name}  ->  {url}")

        try:
            page = fetch_html(url, jitter=1.0, logger=lambda m: log(m))
        except Blocked as exc:
            failures_total += 1
            _record_failure(entry, str(exc), cfg, token, can_send, search.name)
            continue
        except FetchError as exc:
            failures_total += 1
            _record_failure(entry, str(exc), cfg, token, can_send, search.name)
            continue

        if "srchrslt-adtable" not in page:
            failures_total += 1
            _record_failure(
                entry,
                f"Ergebnisliste fehlt im HTML ({len(page)} Zeichen) – Layout geaendert oder Blockseite",
                cfg,
                token,
                can_send,
                search.name,
            )
            continue

        try:
            requires, excludes = compile_rules(search)
        except RuleError as exc:
            print(f"Konfigurationsfehler: {exc}", file=sys.stderr)
            return 1

        listings = parse_listings(page)
        if search.radius_km:
            # Kleinanzeigen ignorert den Radius im serverseitigen HTML -> selbst rechnen.
            listings, unknown = _with_distances(listings, search.zip)
            if unknown:
                log(f"  {unknown} Anzeige(n) ohne PLZ-Zuordnung (Entfernung unbekannt)")

        matched: list[tuple[Listing, int | None]] = []
        dropped: list[tuple[Listing, str]] = []
        for listing in listings:
            ok, reason = evaluate(listing, search, requires=requires, excludes=excludes, now=now)
            if ok:
                matched.append((listing, None))
            else:
                dropped.append((listing, reason))

        entry["failures"] = 0
        entry["alerted"] = False

        if not entry["initialized"] and not args.dry_run:
            for listing in listings:
                state.mark(search.name, listing.adid, listing.price_value)
            entry["initialized"] = True
            log(f"  Baseline gesetzt: {len(listings)} Anzeigen gespeichert, keine Nachricht.")
            continue

        if args.dry_run and not entry["initialized"]:
            log("  Hinweis: Dry-Run auf leerem State – der erste echte Lauf setzt die Baseline.")

        log(f"  {len(listings)} Treffer, {len(matched)} passen, {len(dropped)} aussortiert")

        if args.verbose or args.dry_run:
            for listing, reason in dropped:
                log(f"  {BAD}  {_line(listing)}  ({reason})")

        sent = 0
        for listing, _ in matched:
            if sent >= limit:
                log(f"  … Limit {limit} erreicht, Rest im naechsten Lauf")
                break

            if state.is_seen(search.name, listing.adid):
                previous = state.price_of(search.name, listing.adid)
                if (
                    search.notify_price_drop
                    and previous is not None
                    and listing.price_value is not None
                    and listing.price_value < previous
                ):
                    _deliver(listing, search.name, can_send, token, cfg, args, previous)
                    state.mark(search.name, listing.adid, listing.price_value)
                    sent += 1
                continue

            _deliver(listing, search.name, can_send, token, cfg, args, None)
            state.mark(search.name, listing.adid, listing.price_value)
            sent += 1

        handled_total += sent
        if sent == 0:
            log("  nichts Neues")

    if not args.dry_run:
        state.save()

    failed_all = failures_total > 0 and failures_total >= sum(1 for s in cfg.searches if s.enabled)
    log(f"Fertig: {handled_total} Meldung(en), {failures_total} Fehler")
    return 2 if failed_all else 0


def _with_distances(
    listings: list[Listing], center_plz: str
) -> tuple[list[Listing], int]:
    """Fehlende Entfernungen aus PLZ-Koordinaten ergaenzen.

    Gibt (Anzeigen, Anzahl ohne Zuordnung) zurueck.
    """
    enriched: list[Listing] = []
    unknown = 0
    for listing in listings:
        if listing.distance_km is not None:
            enriched.append(listing)
            continue
        distance = geo.distance_km(center_plz, listing.zip_code)
        if distance is None:
            unknown += 1
            enriched.append(listing)
        else:
            enriched.append(replace(listing, distance_km=distance))
    return enriched, unknown


def _deliver(
    listing: Listing,
    search_name: str,
    can_send: bool,
    token: str,
    cfg: config_module.AppConfig,
    args: argparse.Namespace,
    price_drop: int | None,
) -> None:
    kind = "PREISGEFALLEN" if price_drop is not None else "NEU"
    log(f"  {OK}  [{kind}] {_line(listing)}")
    if args.dry_run:
        return
    if not can_send:
        return
    text = format_listing(listing, search_name, price_drop=price_drop)
    try:
        send_text(token, cfg.telegram.chat_id, text, button_url=listing.url)
    except NotifyError as exc:
        log(f"  Telegram-Fehler: {exc}")


def _record_failure(
    entry: dict,
    message: str,
    cfg: config_module.AppConfig,
    token: str,
    can_send: bool,
    search_name: str,
) -> None:
    entry["failures"] = int(entry.get("failures", 0)) + 1
    log(f"  {BAD}  Abruf fehlgeschlagen: {message} (Fehllauf {entry['failures']})")

    threshold = cfg.telegram.alert_after_failures
    if entry["failures"] >= threshold and not entry.get("alerted") and can_send:
        try:
            send_text(
                token,
                cfg.telegram.chat_id,
                f"⚠️ <b>kleinanzeigen-watch ist blind</b>\n\n"
                f"Suche: {search_name}\n"
                f"Grund: {message}\n"
                f"Fehllaeufe in Folge: {entry['failures']}",
            )
            entry["alerted"] = True
        except NotifyError as exc:
            log(f"  Warnung konnte nicht gesendet werden: {exc}")


def _line(listing: Listing) -> str:
    price = listing.price_text or "n/a"
    location = listing.location
    if listing.distance_km is not None:
        location += f" ({listing.distance_km:.0f} km)"
    return f"{listing.adid}  {price:>12}  {location:28}  {listing.title[:60]}"


if __name__ == "__main__":
    raise SystemExit(main())
