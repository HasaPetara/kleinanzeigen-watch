"""Regeln anwenden: Preis, Alter, require/exclude."""

from __future__ import annotations

import re
from datetime import datetime

from .config import Search
from .parse import Listing


class RuleError(Exception):
    """Ungueltiger Regex in der Konfiguration."""


def compile_rules(search: Search) -> tuple[list[re.Pattern[str]], list[re.Pattern[str]]]:
    try:
        requires = [re.compile(pattern, re.IGNORECASE) for pattern in search.require]
        excludes = [re.compile(pattern, re.IGNORECASE) for pattern in search.exclude]
    except re.error as exc:
        raise RuleError(f"Ungueltiger Regex in Suchauftrag '{search.name}': {exc}") from exc
    return requires, excludes


def evaluate(
    listing: Listing,
    search: Search,
    *,
    requires: list[re.Pattern[str]],
    excludes: list[re.Pattern[str]],
    now: datetime,
) -> tuple[bool, str]:
    """(passt, Begruendung) – Begruendung ist bei True leer."""
    if listing.price_value is not None:
        if search.price_min is not None and listing.price_value < search.price_min:
            return False, f"Preis {listing.price_value} < {search.price_min}"
        if search.price_max is not None and listing.price_value > search.price_max:
            return False, f"Preis {listing.price_value} > {search.price_max}"
    elif listing.price_text:
        return False, f"Preis unklar: {listing.price_text}"

    if (
        search.radius_km
        and listing.distance_km is not None
        and listing.distance_km > search.radius_km
    ):
        return False, f"{listing.distance_km:.0f} km entfernt (max {search.radius_km} km)"

    if search.max_age_hours and listing.posted is not None:
        age_hours = (now - datetime.combine(listing.posted, datetime.min.time())).total_seconds() / 3600
        if age_hours > search.max_age_hours:
            return False, f"zu alt ({age_hours:.0f}h)"

    haystack = listing.haystack
    for pattern in requires:
        if not pattern.search(haystack):
            return False, f"require fehlt: {pattern.pattern}"
    for pattern in excludes:
        if pattern.search(haystack):
            return False, f"exclude trifft: {pattern.pattern}"

    return True, ""
