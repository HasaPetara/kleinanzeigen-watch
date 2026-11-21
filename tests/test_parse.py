"""Tests fuer Parser und Filter.

Die Fixture ist bewusst als cp1252 gespeichert: genau so liefert
Kleinanzeigen die Seite aus, obwohl der Header UTF-8 behauptet.

Aufruf:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from watcher import config as config_module  # noqa: E402
from watcher import geo  # noqa: E402
from watcher.fetch import decode_page  # noqa: E402
from watcher.filters import compile_rules, evaluate  # noqa: E402
from watcher.parse import Listing, parse_listings, parse_price  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "search.html"


def load_fixture() -> str:
    return decode_page(FIXTURE.read_bytes())


def make_listing(**overrides) -> Listing:
    base = dict(
        adid="1",
        href="/s-anzeige/klimageraet-xy/1-176-1",
        title="Midea PortaSplit 3,5 kW",
        description="Neuwertig, mit Rechnung.",
        price_text="700 € VB",
        price_value=700,
        zip_code="41812",
        city="Erkelenz",
        distance_km=5.0,
        posted=date(2026, 11, 20),
        shipping=True,
    )
    base.update(overrides)
    return Listing(**base)


class ParseTests(unittest.TestCase):
    def test_parses_all_articles(self):
        listings = parse_listings(load_fixture())
        self.assertEqual(
            sorted(item.adid for item in listings),
            ["3502413647", "3535534017", "3547601306"],
        )

    def test_fields_of_a_real_listing(self):
        listing = next(l for l in parse_listings(load_fixture()) if l.adid == "3547601306")
        self.assertIn("3,5 kW", listing.title)
        self.assertEqual(listing.price_value, 820)
        self.assertEqual(listing.price_text, "820 € VB")
        self.assertEqual(listing.zip_code, "99734")
        self.assertEqual(listing.city, "Nordhausen")
        self.assertIsNotNone(listing.posted)
        self.assertTrue(listing.url.startswith("https://www.kleinanzeigen.de/s-anzeige/"))

    def test_shipping_flag(self):
        listings = {l.adid: l for l in parse_listings(load_fixture())}
        self.assertTrue(listings["3535534017"].shipping)
        self.assertFalse(listings["3547601306"].shipping)

    def test_distance_location_date_from_snippet(self):
        # Entfernungsangabe erscheint nicht in jeder Seitenvariante,
        # deshalb hier ein eigener Ausschnitt.
        html = (
            '<article data-adid="42" data-href="/s-anzeige/x/42-1-1">'
            '<span>32689 Kalletal</span><span class="ml-xsmall">(ca. 200 km)</span>'
            '<h3><a href="/x">Midea PortaSplit</a></h3>'
            '<p class="my-xsmall text-secondary">770 \u20ac VB</p>'
            '<span>09.10.2026</span></article>'
        )
        listing = parse_listings(html)[0]
        self.assertEqual(listing.distance_km, 200.0)
        self.assertEqual(listing.city, "Kalletal")
        self.assertEqual(listing.zip_code, "32689")
        self.assertEqual(listing.price_value, 770)
        self.assertEqual(listing.posted, date(2026, 10, 9))

    def test_umlauts_survive_encoding(self):
        listing = next(l for l in parse_listings(load_fixture()) if l.adid == "3502413647")
        self.assertIn("ähnlich", listing.title)

    def test_price_variants(self):
        self.assertEqual(parse_price("770 € VB"), ("770 € VB", 770))
        self.assertEqual(parse_price("1.200 €"), ("1.200 €", 1200))
        self.assertEqual(parse_price("Zu verschenken"), ("Zu verschenken", 0))
        self.assertEqual(parse_price("VB"), ("VB", None))
        self.assertEqual(parse_price(""), ("", None))


class FilterTests(unittest.TestCase):
    def setUp(self):
        # Bewusst eigene Werte statt config.toml: sonst schlagen die Tests fehl,
        # sobald jemand in der Config Preis oder Umkreis anpasst.
        self.search = config_module.Search(
            name="Midea PortaSplit",
            keyword="portasplit",
            zip="41812",
            radius_km=200,
            price_min=400,
            price_max=850,
            require=["midea", r"porta\s*-?\s*split"],
            exclude=[
                r"porta\s*-?\s*split\s*-?\s*cool",
                r"\b8[.,]?000\b",
                "ähnlich|aehnlich|vergleichbar",
            ],
        )
        self.requires, self.excludes = compile_rules(self.search)
        self.now = datetime(2026, 11, 21, 12, 0)

    def check(self, listing: Listing) -> tuple[bool, str]:
        return evaluate(
            listing,
            self.search,
            requires=self.requires,
            excludes=self.excludes,
            now=self.now,
        )

    def test_real_midea_passes(self):
        ok, reason = self.check(make_listing())
        self.assertTrue(ok, reason)

    def test_spaced_spelling_passes(self):
        ok, _ = self.check(make_listing(title="Midea Porta Split 3,5 kW"))
        self.assertTrue(ok)

    def test_cool_model_is_rejected(self):
        ok, reason = self.check(make_listing(title="Midea PortaSplit Cool Klimaanlage"))
        self.assertFalse(ok)
        self.assertIn("exclude", reason)

    def test_8000_btu_is_rejected(self):
        ok, reason = self.check(make_listing(title="Midea PortaSplit 8000 BTU"))
        self.assertFalse(ok)
        self.assertIn("exclude", reason)

    def test_similar_but_not_midea_is_rejected(self):
        ok, reason = self.check(
            make_listing(title="Mobile Split-Klimaanlage (ähnlich Midea PortaSplit)")
        )
        self.assertFalse(ok)
        self.assertIn("exclude", reason)

    def test_other_brand_is_rejected(self):
        ok, reason = self.check(make_listing(title="Evolar PortaSplit Klimagerät"))
        self.assertFalse(ok)
        self.assertIn("require", reason)

    def test_price_above_window_is_rejected(self):
        ok, reason = self.check(make_listing(price_text="900 €", price_value=900))
        self.assertFalse(ok)
        self.assertIn("900", reason)

    def test_price_below_window_is_rejected(self):
        ok, reason = self.check(make_listing(price_text="300 €", price_value=300))
        self.assertFalse(ok)
        self.assertIn("300", reason)

    def test_unknown_price_is_rejected(self):
        ok, reason = self.check(make_listing(price_text="VB", price_value=None))
        self.assertFalse(ok)
        self.assertIn("unklar", reason)

    def test_too_far_away_is_rejected(self):
        ok, reason = self.check(make_listing(zip_code="91090", distance_km=380.0))
        self.assertFalse(ok)
        self.assertIn("380 km", reason)

    def test_unknown_distance_is_kept(self):
        ok, reason = self.check(make_listing(zip_code="", distance_km=None))
        self.assertTrue(ok, reason)

    def test_old_listing_is_rejected_when_age_limit_set(self):
        search = config_module.Search(
            name="x", keyword="portasplit", max_age_hours=24, price_min=400, price_max=850
        )
        requires, excludes = compile_rules(search)
        ok, reason = evaluate(
            make_listing(posted=date(2026, 11, 1)),
            search,
            requires=requires,
            excludes=excludes,
            now=self.now,
        )
        self.assertFalse(ok)
        self.assertIn("alt", reason)


class GeoTests(unittest.TestCase):
    def test_known_coordinates(self):
        self.assertAlmostEqual(geo.coords("41812")[0], 51.08, places=1)

    def test_distance_erkelenz_to_effeltrich(self):
        distance = geo.distance_km("41812", "91090")
        self.assertIsNotNone(distance)
        self.assertGreater(distance, 350)

    def test_distance_to_self_is_zero(self):
        self.assertEqual(geo.distance_km("41812", "41812"), 0.0)

    def test_unknown_plz_gives_none(self):
        self.assertIsNone(geo.distance_km("41812", "99999"))
        self.assertIsNone(geo.distance_km("41812", ""))


class UrlTests(unittest.TestCase):
    def test_url_contains_filters_and_no_l1202(self):
        url = config_module.Search(
            name="x", keyword="portasplit", zip="41812", radius_km=200,
            price_min=400, price_max=850,
        ).url()
        self.assertIn("/s-sortierung:neueste/41812/anzeige:angebote/preis:400:850/portasplit/k0r200", url)
        self.assertNotIn("l1202", url)

    def test_url_without_price_segment(self):
        url = config_module.Search(name="x", keyword="midea portasplit", zip="41812", radius_km=50).url()
        self.assertNotIn("preis:", url)
        self.assertTrue(url.endswith("/midea-portasplit/k0r50"))

    def test_shipped_config_is_valid(self):
        cfg = config_module.load(PROJECT_ROOT / "config.toml")
        self.assertEqual(len(cfg.searches), 1)
        self.assertEqual(cfg.searches[0].keyword, "portasplit")


if __name__ == "__main__":
    unittest.main()
