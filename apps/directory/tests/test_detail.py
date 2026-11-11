from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse

from apps.directory.models import Business, Category, Offering

User = get_user_model()
DORAL = Point(-80.3553, 25.8195, srid=4326)


class BusinessDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(email="owner@example.com", password="x", first_name="Carla")
        cls.other = User.objects.create_user(email="other@example.com", password="x")
        cls.staff = User.objects.create_user(email="staff@example.com", password="x", is_staff=True)
        cls.category = Category.objects.create(name="Bakery", slug="bakery")
        cls.business = Business.objects.create(
            owner=cls.owner,
            category=cls.category,
            name="La Casa del Golfeado",
            description="Family bakery.",
            status=Business.Status.APPROVED,
            location=DORAL,
            address="123 NW 41st St, Doral, FL",
            phone="(305) 555-0100",
            website="https://example.com/bakery",
            instagram="example_bakery",
            offers_delivery=True,
            offerings=[
                Offering(name="Golfeados", description="Sweet rolls", price_from=Decimal("12"), price_note="per dozen"),
                Offering(name="Party trays"),
            ],
        )

    def create(self, **kwargs):
        kwargs.setdefault("name", "Other Place")
        return Business.objects.create(owner=self.owner, category=self.category, location=DORAL, **kwargs)

    def detail(self, business=None):
        return self.client.get(reverse("directory:detail", args=[(business or self.business).slug]))

    def test_approved_detail_200_shows_offerings_and_prices(self):
        res = self.detail()
        self.assertContains(res, "<html")
        self.assertContains(res, "La Casa del Golfeado")
        self.assertContains(res, "Bakery")
        self.assertContains(res, "Family bakery.")
        self.assertContains(res, "Sweet rolls")
        self.assertContains(res, "From $12.00 per dozen")

    def test_offering_without_price_shows_ask_for_price(self):
        self.assertContains(self.detail(), "Ask for price")

    def test_active_since_years(self):
        cases = [(None, "Active since N/A"), (date(2026, 3, 1), "Active since 2026 · less than a year"),
                 (date(2025, 1, 10), "Active since 2025 · 1 year"), (date(2019, 2, 1), "Active since 2019 · 7 years")]
        with mock.patch("apps.directory.models.timezone.localdate", return_value=date(2026, 6, 15)):
            for started_on, text in cases:
                with self.subTest(started_on=started_on):
                    Business.objects.filter(pk=self.business.pk).update(started_on=started_on)
                    self.assertContains(self.detail(), text)

    def test_rating_summary(self):
        self.assertContains(self.detail(), "No reviews yet")
        Business.objects.filter(pk=self.business.pk).update(rating_sum=52, rating_count=12)
        res = self.detail()
        self.assertContains(res, "<strong>4.3</strong>")
        self.assertContains(res, "(12 reviews)")
        self.assertNotContains(res, "No reviews yet")

    def test_pending_404_for_anonymous_and_other_user(self):
        pending = self.create()
        self.assertEqual(self.detail(pending).status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.detail(pending).status_code, 404)
        panel = self.client.get(reverse("directory:panel", args=[pending.slug]))
        self.assertEqual(panel.status_code, 404)

    def test_pending_200_for_owner_with_status_banner(self):
        self.client.force_login(self.owner)
        res = self.detail(self.create())
        self.assertContains(res, "Pending review")
        self.assertContains(res, "Only you and moderators can see this page")

    def test_approved_has_no_status_banner_for_owner(self):
        self.client.force_login(self.owner)
        self.assertNotContains(self.detail(), "status-banner")

    def test_rejected_shows_reason_to_owner_only(self):
        rejected = self.create(status=Business.Status.REJECTED, rejection_reason="Please add prices.")
        self.client.force_login(self.owner)
        res = self.detail(rejected)
        self.assertContains(res, "Needs changes")
        self.assertContains(res, "Please add prices.")
        self.client.force_login(self.staff)
        res = self.detail(rejected)
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, "Please add prices.")

    def test_staff_can_view_pending(self):
        self.client.force_login(self.staff)
        self.assertContains(self.detail(self.create()), "Pending review")

    def test_panel_is_partial(self):
        res = self.client.get(reverse("directory:panel", args=[self.business.slug]), headers={"HX-Request": "true"})
        self.assertContains(res, "La Casa del Golfeado")
        self.assertContains(res, "From $12.00 per dozen")
        self.assertContains(res, f'href="{reverse("directory:detail", args=[self.business.slug])}"')
        self.assertNotContains(res, "<html")

    def test_vendor_text_escaped(self):
        Business.objects.filter(pk=self.business.pk).update(description="<script>alert(1)</script>")
        res = self.detail()
        self.assertNotContains(res, "<script>alert(1)</script>")
        self.assertContains(res, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_website_non_http_scheme_not_linked(self):
        Business.objects.filter(pk=self.business.pk).update(website="javascript:alert(1)")
        res = self.detail()
        self.assertNotContains(res, 'href="javascript:')
        self.assertNotContains(res, "alert(1)")

    def test_external_links_rel_and_phone_href(self):
        res = self.detail()
        self.assertContains(
            res, '<a href="https://example.com/bakery" rel="noopener nofollow ugc" target="_blank">', html=False
        )
        self.assertContains(res, 'href="tel:3055550100"')

    def test_unknown_slug_404(self):
        self.assertEqual(self.client.get(reverse("directory:detail", args=["nope"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("directory:panel", args=["nope"])).status_code, 404)

    def test_instagram_link_built_from_handle(self):
        self.assertContains(
            self.detail(),
            '<a href="https://www.instagram.com/example_bakery/" rel="noopener nofollow ugc" target="_blank">@example_bakery</a>',
            html=True,
        )
        Business.objects.filter(pk=self.business.pk).update(instagram="")
        self.assertNotContains(self.detail(), "instagram.com")

    def test_delivery_badge_only_when_offered(self):
        self.assertContains(self.detail(), "Offers delivery")
        Business.objects.filter(pk=self.business.pk).update(offers_delivery=False)
        self.assertNotContains(self.detail(), "Offers delivery")

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post(reverse("directory:detail", args=[self.business.slug])).status_code, 405)
