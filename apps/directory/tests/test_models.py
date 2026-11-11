from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase

from apps.directory.models import Business, Category, Offering

DORAL = Point(-80.3553, 25.8195, srid=4326)


def make_business(owner, category, **kwargs):
    kwargs.setdefault("name", "La Casa del Golfeado")
    kwargs.setdefault("location", DORAL)
    return Business.objects.create(owner=owner, category=category, **kwargs)


class BusinessModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(email="owner@example.com", password="x")
        cls.bakery = Category.objects.create(name="Bakery", slug="bakery")

    def test_search_terms_include_offerings(self):
        business = make_business(
            self.owner,
            self.bakery,
            description="Recién horneado",
            offerings=[Offering(name="Golfeados", description="Con queso", price_from=Decimal("3.50"))],
        )
        for term in ("golfeado", "queso", "bakery", "casa", "horneado"):
            self.assertIn(term, business.search_terms)

    def test_search_terms_refresh_on_save(self):
        business = make_business(self.owner, self.bakery)
        business.offerings = [Offering(name="Cachitos")]
        business.save()
        business.refresh_from_db()
        self.assertIn("cachito", business.search_terms)

    def test_approved_queryset_excludes_pending_and_rejected(self):
        approved = make_business(self.owner, self.bakery, name="A", status=Business.Status.APPROVED)
        make_business(self.owner, self.bakery, name="P")
        make_business(self.owner, self.bakery, name="R", status=Business.Status.REJECTED)
        self.assertEqual(list(Business.objects.approved()), [approved])

    def test_new_business_is_pending(self):
        self.assertEqual(make_business(self.owner, self.bakery).status, Business.Status.PENDING)

    def test_slug_generated_and_unique(self):
        first = make_business(self.owner, self.bakery, name="Café Piñata")
        second = make_business(self.owner, self.bakery, name="Café Piñata")
        third = make_business(self.owner, self.bakery, name="Cafe pinata!")
        self.assertEqual([first.slug, second.slug, third.slug], ["cafe-pinata", "cafe-pinata-2", "cafe-pinata-3"])

    def test_slug_fallback_for_unsluggable_name(self):
        self.assertEqual(make_business(self.owner, self.bakery, name="🥐🥐").slug, "business")

    def test_slug_stable_on_rename(self):
        business = make_business(self.owner, self.bakery, name="Old Name")
        business.name = "New Name"
        business.save()
        business.refresh_from_db()
        self.assertEqual(business.slug, "old-name")

    def test_years_active_none_zero_and_anniversary(self):
        business = Business(started_on=None)
        self.assertIsNone(business.years_active)
        with mock.patch("apps.directory.models.timezone.localdate", return_value=date(2026, 6, 15)):
            business.started_on = date(2026, 1, 1)
            self.assertEqual(business.years_active, 0)
            business.started_on = date(2023, 6, 15)
            self.assertEqual(business.years_active, 3)
            business.started_on = date(2023, 6, 16)
            self.assertEqual(business.years_active, 2)

    def test_rating_avg(self):
        business = Business()
        self.assertIsNone(business.rating_avg)
        business.rating_sum, business.rating_count = 14, 3
        self.assertEqual(business.rating_avg, 4.7)

    def test_instagram_handle_validation(self):
        field = Business._meta.get_field("instagram")
        self.assertEqual(field.clean("la_casa.golfeado", None), "la_casa.golfeado")
        for bad in ("@la_casa", "https://instagram.com/x", "la casa", "a" * 31):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                field.clean(bad, None)

    def test_offers_delivery_defaults_false(self):
        self.assertFalse(make_business(self.owner, self.bakery).offers_delivery)

    def test_offerings_round_trip(self):
        business = make_business(
            self.owner,
            self.bakery,
            offerings=[
                Offering(name="Golfeados", price_from=Decimal("3.50"), price_note="each"),
                Offering(name="Tortas"),
            ],
        )
        business = Business.objects.get(pk=business.pk)
        self.assertEqual([o.name for o in business.offerings], ["Golfeados", "Tortas"])
        self.assertIsInstance(business.offerings[0].price_from, Decimal)
        self.assertEqual(business.offerings[0].price_from, Decimal("3.50"))
        self.assertIsNone(business.offerings[1].price_from)

    def test_location_has_2dsphere_index(self):
        indexes = connection.get_collection(Business._meta.db_table).index_information()
        keys = [dict(info["key"]) for info in indexes.values()]
        self.assertIn({"location": "2dsphere"}, keys)


class CategoryModelTests(TestCase):
    def test_ordered_by_name(self):
        Category.objects.create(name="Music Lessons", slug="music-lessons")
        Category.objects.create(name="Bakery", slug="bakery")
        self.assertEqual([c.name for c in Category.objects.all()], ["Bakery", "Music Lessons"])
