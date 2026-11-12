from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, Polygon
from django.test import TestCase

from apps.directory.models import Business, Category
from apps.geo.queries import in_bbox, near, nearest

ORIGIN = Point(-80.3553, 25.8195, srid=4326)  # Doral, FL


class GeoQueryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        owner = get_user_model().objects.create_user(email="geo@example.com", password="x")
        category = Category.objects.create(name="Test", slug="test")

        def make(name, lat):
            return Business.objects.create(
                owner=owner, category=category, name=name, location=Point(-80.3553, lat, srid=4326)
            )

        # ~0.009° latitude ≈ 1 km.
        cls.at_origin = make("origin", 25.8195)
        cls.one_km = make("1km", 25.8285)
        cls.ten_km = make("10km", 25.9095)

    def test_near_respects_radius(self):
        names = set(near(Business.objects.all(), ORIGIN, 2).values_list("name", flat=True))
        self.assertEqual(names, {"origin", "1km"})

    def test_in_bbox(self):
        bbox = Polygon.from_bbox((-80.40, 25.81, -80.30, 25.83))
        names = set(in_bbox(Business.objects.all(), bbox).values_list("name", flat=True))
        self.assertEqual(names, {"origin", "1km"})

    def test_nearest_sorted_with_distance(self):
        results = list(nearest(Business, ORIGIN, 20, limit=10))
        self.assertEqual([p.name for p in results], ["origin", "1km", "10km"])
        self.assertAlmostEqual(results[1].distance_m, 1000, delta=20)

    def test_nearest_limit(self):
        self.assertEqual(len(list(nearest(Business, ORIGIN, 20, limit=1))), 1)

    def test_nearest_with_query_filters(self):
        results = list(nearest(Business, ORIGIN, 20, limit=10, query={"name": {"$in": ["10km", "1km"]}}))
        self.assertEqual([p.name for p in results], ["1km", "10km"])

    def test_nearest_without_query_unchanged(self):
        results = list(nearest(Business, ORIGIN, 20, limit=10, query=None))
        self.assertEqual([p.name for p in results], ["origin", "1km", "10km"])
