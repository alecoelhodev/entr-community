from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse

from apps.places.models import Place


class PlaceViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Place.objects.create(name="Here", location=Point(-9.1366, 38.7076, srid=4326))
        Place.objects.create(name="Far", location=Point(-8.0, 40.0, srid=4326))

    def test_map_page(self):
        res = self.client.get(reverse("places:map"))
        self.assertContains(res, 'x-data="placesMap"')
        self.assertIn("tile.openstreetmap.org", res.headers["Content-Security-Policy"])

    def test_geojson(self):
        res = self.client.get(reverse("places:geojson"), {"bbox": "-9.2,38.6,-9.0,38.8"})
        self.assertEqual(res.status_code, 200)
        features = res.json()["features"]
        self.assertEqual([f["properties"]["name"] for f in features], ["Here"])
        self.assertEqual(features[0]["geometry"]["coordinates"], [-9.1366, 38.7076])

    def test_geojson_rejects_bad_bbox(self):
        res = self.client.get(reverse("places:geojson"), {"bbox": "-180,-90,180,90"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("bbox", res.json()["errors"])

    def test_nearby_partial(self):
        res = self.client.get(
            reverse("places:nearby"),
            {"lat": "38.7076", "lng": "-9.1366", "radius_km": "5"},
            headers={"HX-Request": "true"},
        )
        self.assertContains(res, "Here")
        self.assertNotContains(res, "Far")
        self.assertNotContains(res, "<html")

    def test_nearby_invalid(self):
        res = self.client.get(reverse("places:nearby"), {"lat": "100", "lng": "0"})
        self.assertContains(res, "Invalid location", status_code=400)
