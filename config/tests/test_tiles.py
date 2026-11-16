from django.test import SimpleTestCase

from config.tiles import tile_config

MAPTILER_URL = "https://api.maptiler.com/maps/streets-v4/256/{z}/{x}/{y}.png?key=SECRETKEY123"


class TileConfigTests(SimpleTestCase):
    def test_maptiler_origin_and_attribution(self):
        origin, attribution = tile_config(MAPTILER_URL)
        self.assertEqual(origin, "https://api.maptiler.com")
        self.assertIn('href="https://www.maptiler.com/copyright/"', attribution)
        self.assertIn("&copy; MapTiler", attribution)
        self.assertIn('href="https://www.openstreetmap.org/copyright"', attribution)
        self.assertIn("OpenStreetMap contributors", attribution)

    def test_osm_default_attribution(self):
        origin, attribution = tile_config("https://tile.openstreetmap.org/{z}/{x}/{y}.png")
        self.assertEqual(origin, "https://tile.openstreetmap.org")
        self.assertIn('href="https://www.openstreetmap.org/copyright"', attribution)
        self.assertNotIn("MapTiler", attribution)

    def test_subdomain_placeholder_becomes_wildcard(self):
        origin, _ = tile_config("https://{s}.tile.example.com/{z}/{x}/{y}.png")
        self.assertEqual(origin, "https://*.tile.example.com")

    def test_attribution_has_no_key(self):
        origin, attribution = tile_config(MAPTILER_URL)
        self.assertNotIn("SECRETKEY123", attribution)
        self.assertNotIn("SECRETKEY123", origin)

    def test_lookalike_host_is_not_maptiler(self):
        _, attribution = tile_config("https://api.maptiler.com.evil.example/{z}/{x}/{y}.png")
        self.assertNotIn("MapTiler", attribution)
