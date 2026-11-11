from django.contrib.gis.geos import Point, Polygon
from django.test import TestCase

from apps.geo.queries import in_bbox, near, nearest
from apps.places.models import Place

ORIGIN = Point(-9.1366, 38.7076, srid=4326)  # Praça do Comércio


class GeoQueryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # ~0.009° latitude ≈ 1 km.
        cls.at_origin = Place.objects.create(name="origin", location=ORIGIN)
        cls.one_km = Place.objects.create(name="1km", location=Point(-9.1366, 38.7166, srid=4326))
        cls.ten_km = Place.objects.create(name="10km", location=Point(-9.1366, 38.7976, srid=4326))

    def test_near_respects_radius(self):
        names = set(near(Place.objects.all(), ORIGIN, 2).values_list("name", flat=True))
        self.assertEqual(names, {"origin", "1km"})

    def test_in_bbox(self):
        bbox = Polygon.from_bbox((-9.2, 38.70, -9.1, 38.72))
        names = set(in_bbox(Place.objects.all(), bbox).values_list("name", flat=True))
        self.assertEqual(names, {"origin", "1km"})

    def test_nearest_sorted_with_distance(self):
        results = list(nearest(Place, ORIGIN, 20, limit=10))
        self.assertEqual([p.name for p in results], ["origin", "1km", "10km"])
        self.assertAlmostEqual(results[1].distance_m, 1000, delta=20)

    def test_nearest_limit(self):
        self.assertEqual(len(list(nearest(Place, ORIGIN, 20, limit=1))), 1)

    def test_nearest_with_query_filters(self):
        results = list(nearest(Place, ORIGIN, 20, limit=10, query={"name": {"$in": ["10km", "1km"]}}))
        self.assertEqual([p.name for p in results], ["1km", "10km"])

    def test_nearest_without_query_unchanged(self):
        results = list(nearest(Place, ORIGIN, 20, limit=10, query=None))
        self.assertEqual([p.name for p in results], ["origin", "1km", "10km"])
