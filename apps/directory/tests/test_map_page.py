import re

from django.test import TestCase
from django.urls import reverse

from apps.directory.models import Category


class MapPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Category.objects.create(name="Bakery", slug="bakery")
        Category.objects.create(name="Printing & Apparel", slug="printing-apparel")

    def setUp(self):
        self.res = self.client.get("/")

    def test_home_is_directory_map(self):
        self.assertEqual(reverse("directory:map"), "/")
        self.assertContains(self.res, 'x-data="directoryMap"')
        self.assertContains(self.res, "js/map.js")

    def test_data_attributes_present(self):
        for attr in (
            f'data-geojson-url="{reverse("directory:geojson")}"',
            f'data-nearby-url="{reverse("directory:nearby")}"',
            'data-panel-url="/b/__slug__/panel/"',
            'data-center-lat="25.8195"',
            'data-center-lng="-80.3553"',
            'data-zoom="13"',
            'data-tile-url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"',
        ):
            with self.subTest(attr=attr):
                self.assertContains(self.res, attr)

    def test_category_options_rendered(self):
        self.assertContains(self.res, '<option value="">All categories</option>', html=True)
        self.assertContains(self.res, '<option value="bakery">Bakery</option>', html=True)
        self.assertContains(self.res, '<option value="printing-apparel">Printing &amp; Apparel</option>', html=True)

    def test_search_input_has_maxlength_100(self):
        self.assertRegex(self.res.content.decode(), r'<input[^>]*type="search"[^>]*maxlength="100"')

    def test_detail_and_results_regions(self):
        self.assertContains(self.res, 'id="detail"')
        self.assertContains(self.res, 'id="nearby"')

    def test_csp_header_allows_tile_origin(self):
        self.assertIn("tile.openstreetmap.org", self.res.headers["Content-Security-Policy"])

    def test_no_inline_script_or_style(self):
        html = self.res.content.decode()
        self.assertEqual(re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", html), [])
        self.assertNotIn(" style=", html)
        self.assertNotIn("<style", html)

    def test_header_brand_links_home(self):
        self.assertContains(self.res, f'href="{reverse("directory:map")}" class="brand"')


class PanelControlsTests(TestCase):
    def test_panel_has_close_controls(self):
        from .factories import directory_fixture

        directory_fixture(self)
        res = self.client.get(reverse("directory:panel", args=[self.bakery.slug]))
        self.assertContains(res, '@click="closePanel"')
        self.assertContains(res, "Back to results")

    def test_full_page_has_no_panel_controls(self):
        from .factories import directory_fixture

        directory_fixture(self)
        res = self.client.get(reverse("directory:detail", args=[self.bakery.slug]))
        self.assertNotContains(res, "closePanel")


class NearbyCardTests(TestCase):
    def test_cards_open_panel_and_heading_names_query(self):
        from .factories import directory_fixture

        directory_fixture(self)
        res = self.client.get(
            reverse("directory:nearby"), {"lat": "25.8195", "lng": "-80.3553", "q": "golfeados"}
        )
        self.assertContains(res, 'data-slug="la-casa-del-golfeado"')
        self.assertContains(res, '@click.prevent="openFromCard"')
        self.assertContains(res, "“golfeados” within 5 km")
