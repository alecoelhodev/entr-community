from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Polygon
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.directory.models import Business, Category

DORAL_BBOX = (-80.40, 25.78, -80.30, 25.86)
SEED_EMAIL = "seed@example.invalid"


def seed():
    call_command("seed_directory", verbosity=0)


class SeedDirectoryTests(TestCase):
    def test_seed_creates_approved_businesses_in_doral(self):
        seed()
        businesses = Business.objects.all()
        self.assertGreaterEqual(businesses.count(), 8)
        self.assertEqual(businesses.filter(status=Business.Status.APPROVED).count(), businesses.count())
        inside = businesses.filter(location__within=Polygon.from_bbox(DORAL_BBOX)).count()
        self.assertEqual(inside, businesses.count())
        self.assertEqual({b.owner.email for b in businesses.select_related("owner")}, {SEED_EMAIL})

    def test_seed_categories(self):
        seed()
        names = set(Category.objects.values_list("name", flat=True))
        for name in ("Bakery", "Printing & Apparel", "Music Lessons", "Food Truck", "Beauty", "Home Services"):
            self.assertIn(name, names)

    def test_seed_variety(self):
        seed()
        self.assertTrue(Business.objects.filter(offers_delivery=True).exists())
        self.assertTrue(Business.objects.filter(offers_delivery=False).exists())
        self.assertTrue(Business.objects.exclude(instagram="").exists())
        self.assertGreater(len(set(Business.objects.values_list("started_on", flat=True))), 3)
        for business in Business.objects.exclude(instagram=""):
            self.assertTrue(business.instagram.startswith("example_"), business.instagram)

    def test_seed_idempotent(self):
        seed()
        counts = (Business.objects.count(), Category.objects.count(), get_user_model().objects.count())
        seed()
        self.assertEqual((Business.objects.count(), Category.objects.count(), get_user_model().objects.count()), counts)

    def test_seed_data_searchable(self):
        seed()
        bbox = ",".join(str(v) for v in DORAL_BBOX)

        def names(q):
            res = self.client.get(reverse("directory:geojson"), {"bbox": bbox, "q": q})
            return {f["properties"]["name"] for f in res.json()["features"]}

        self.assertIn("La Casa del Golfeado", names("golfeados"))
        self.assertIn("Andrés Guitar Lessons", names("guitar"))
        self.assertIn("Doral Print Lab", names("t-shirt printing"))
        self.assertNotIn("Andrés Guitar Lessons", names("golfeados"))

    def test_seed_user_cannot_log_in(self):
        seed()
        user = get_user_model().objects.get(email=SEED_EMAIL)
        self.assertFalse(user.has_usable_password())
        self.assertFalse(self.client.login(email=SEED_EMAIL, password=""))
