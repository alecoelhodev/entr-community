from unittest import mock

from django.test import TestCase
from django.urls import reverse_lazy

from .factories import DORAL_BBOX, directory_fixture

BAKERY = {"lat": "25.8195", "lng": "-80.3553"}


class BusinessGeoJSONTests(TestCase):
    url = reverse_lazy("directory:geojson")

    @classmethod
    def setUpTestData(cls):
        directory_fixture(cls)

    def names(self, **params):
        res = self.client.get(self.url, {"bbox": DORAL_BBOX, **params})
        self.assertEqual(res.status_code, 200, res.content)
        return sorted(f["properties"]["name"] for f in res.json()["features"])

    def test_geojson_returns_only_approved_in_bbox(self):
        self.assertEqual(self.names(), ["Doral Print Lab", "La Casa del Golfeado", "Profe Luis Guitar"])

    def test_geojson_feature_properties_whitelist(self):
        res = self.client.get(self.url, {"bbox": DORAL_BBOX, "q": "golfeados"})
        (feature,) = res.json()["features"]
        self.assertEqual(
            feature["properties"],
            {
                "id": str(self.bakery.pk),
                "slug": "la-casa-del-golfeado",
                "name": "La Casa del Golfeado",
                "category": "Bakery",
                "rating_avg": 4.7,
                "offers_delivery": False,
            },
        )

    def test_geojson_coordinates_lng_lat(self):
        res = self.client.get(self.url, {"bbox": DORAL_BBOX, "q": "golfeados"})
        self.assertEqual(res.json()["features"][0]["geometry"]["coordinates"], [-80.3553, 25.8195])

    def test_geojson_filters_by_category(self):
        self.assertEqual(self.names(category="music-lessons"), ["Profe Luis Guitar"])

    def test_geojson_search_matches_offering(self):
        self.assertEqual(self.names(q="golfeados"), ["La Casa del Golfeado"])
        self.assertEqual(self.names(q="T-Shirt"), ["Doral Print Lab"])

    def test_geojson_search_all_terms_required(self):
        self.assertEqual(self.names(q="golfeados printing"), [])

    def test_geojson_stopword_only_query_applies_no_filter(self):
        self.assertEqual(len(self.names(q="de la")), 3)

    def test_geojson_category_and_search_combined(self):
        self.assertEqual(self.names(category="bakery", q="cachitos"), ["La Casa del Golfeado"])
        self.assertEqual(self.names(category="music-lessons", q="cachitos"), [])

    def test_geojson_bad_category_400(self):
        res = self.client.get(self.url, {"bbox": DORAL_BBOX, "category": "nope"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("category", res.json()["errors"])

    def test_geojson_q_too_long_400(self):
        res = self.client.get(self.url, {"bbox": DORAL_BBOX, "q": "x" * 101})
        self.assertEqual(res.status_code, 400)
        self.assertIn("q", res.json()["errors"])

    def test_geojson_bad_bbox_400(self):
        res = self.client.get(self.url, {"bbox": "-180,-90,180,90"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("bbox", res.json()["errors"])

    def test_geojson_cap_500(self):
        with mock.patch("apps.directory.views.MAX_MAP_FEATURES", 2):
            self.assertEqual(len(self.names()), 2)

    def test_geojson_category_names_without_n_plus_one(self):
        with self.assertNumQueries(1):
            self.client.get(self.url, {"bbox": DORAL_BBOX})

    def test_geojson_rejects_post(self):
        self.assertEqual(self.client.post(self.url, {"bbox": DORAL_BBOX}).status_code, 405)


class BusinessNearbyTests(TestCase):
    url = reverse_lazy("directory:nearby")

    @classmethod
    def setUpTestData(cls):
        directory_fixture(cls)

    def get(self, **params):
        return self.client.get(self.url, {**BAKERY, "radius_km": "5", **params}, headers={"HX-Request": "true"})

    def test_nearby_sorted_by_distance_and_filtered(self):
        res = self.get()
        self.assertEqual(
            [b.name for b in res.context["businesses"]],
            ["La Casa del Golfeado", "Profe Luis Guitar", "Doral Print Lab"],
        )
        res = self.get(q="golfeados")
        self.assertEqual([b.name for b in res.context["businesses"]], ["La Casa del Golfeado"])
        res = self.get(category="printing-apparel")
        self.assertEqual([b.name for b in res.context["businesses"]], ["Doral Print Lab"])

    def test_nearby_excludes_pending(self):
        self.assertNotContains(self.get(radius_km="50"), "Pending Panadería")

    def test_nearby_row_content(self):
        res = self.get()
        self.assertContains(res, "Printing &amp; Apparel")
        self.assertContains(res, "Delivery", count=1)
        self.assertContains(res, "4.7")
        self.assertContains(res, "No reviews yet")
        self.assertContains(res, "0 m")

    def test_nearby_is_partial(self):
        res = self.get()
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, "<html")

    def test_nearby_invalid_400(self):
        res = self.client.get(self.url, {"lat": "100", "lng": "0"})
        self.assertContains(res, "Invalid location", status_code=400)

    def test_nearby_invalid_filter_400(self):
        res = self.get(category="nope")
        self.assertEqual(res.status_code, 400)
        self.assertNotContains(res, "nope", status_code=400)

    def test_nearby_category_names_in_one_extra_query(self):
        with self.assertNumQueries(2):
            self.get()
