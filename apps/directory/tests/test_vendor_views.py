from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import Client, TestCase
from django.urls import reverse, reverse_lazy
from django.utils import timezone

from apps.directory.models import Business, Category, Offering

User = get_user_model()
DORAL = Point(-80.3553, 25.8195, srid=4326)


def form_data(category, **overrides):
    data = {
        "name": "Andrés Guitar Lessons",
        "category": str(category.pk),
        "description": "Lessons for kids and adults.",
        "started_on": "2018-03-01",
        "lat": "25.8195",
        "lng": "-80.3553",
        "address": "",
        "phone": "(305) 555-0100",
        "website": "https://example.com",
        "instagram": "",
        "offerings-TOTAL_FORMS": "3",
        "offerings-INITIAL_FORMS": "0",
        "offerings-MIN_NUM_FORMS": "0",
        "offerings-MAX_NUM_FORMS": "10",
        "offerings-0-name": "Guitar lessons",
        "offerings-0-price_from": "35.00",
        "offerings-0-price_note": "per hour",
        "offerings-0-description": "",
        "offerings-1-name": "Golfeados",
        "offerings-1-price_from": "2.50",
        "offerings-1-price_note": "each",
        "offerings-1-description": "",
        "offerings-2-name": "",
        "offerings-2-price_from": "",
        "offerings-2-price_note": "",
        "offerings-2-description": "",
    }
    data.update(overrides)
    return data


class VendorTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email="andres@example.com", password="x", first_name="Andrés")
        cls.other = User.objects.create_user(email="other@example.com", password="x")
        cls.category = Category.objects.create(name="Music Lessons", slug="music-lessons")

    def setUp(self):
        self.client.force_login(self.user)

    def make(self, owner=None, **kwargs):
        kwargs.setdefault("name", "Existing")
        kwargs.setdefault("offerings", [Offering(name="Lessons")])
        return Business.objects.create(owner=owner or self.user, category=self.category, location=DORAL, **kwargs)


class VendorDashboardTests(VendorTestCase):
    url = reverse_lazy("directory:my_businesses")

    def test_dashboard_requires_login(self):
        self.client.logout()
        res = self.client.get(self.url)
        self.assertRedirects(res, f"{reverse('accounts:login')}?next={self.url}", fetch_redirect_response=False)

    def test_dashboard_lists_only_own_businesses_with_status(self):
        self.make(name="Mine Approved", status=Business.Status.APPROVED)
        self.make(name="Mine Pending")
        self.make(name="Mine Rejected", status=Business.Status.REJECTED, rejection_reason="Add a price.")
        self.make(owner=self.other, name="Not Mine")
        res = self.client.get(self.url)
        for text in ("Mine Approved", "Approved · live on the map", "Mine Pending", "Pending review",
                     "Mine Rejected", "Needs changes", "Add a price."):
            self.assertContains(res, text)
        self.assertNotContains(res, "Not Mine")
        self.assertContains(res, f'href="{reverse("directory:business_create")}"')

    def test_header_links_to_dashboard_when_logged_in(self):
        self.assertContains(self.client.get("/"), f'href="{self.url}"')


class BusinessCreateTests(VendorTestCase):
    url = reverse_lazy("directory:business_create")

    def post(self, **overrides):
        return self.client.post(self.url, form_data(self.category, **overrides))

    def assertFieldError(self, res, field):
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Please fix the highlighted fields.")
        self.assertIn(field, res.context["form"].errors)
        self.assertFalse(Business.objects.exists())

    def test_create_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.post()
        self.assertFalse(Business.objects.exists())

    def test_create_form_renders_picker_and_offering_rows(self):
        res = self.client.get(self.url)
        self.assertContains(res, 'x-data="locationPicker"')
        self.assertContains(res, 'name="offerings-0-name"')
        self.assertContains(res, "js/location-picker.js")

    def test_create_sets_owner_and_pending(self):
        res = self.post()
        self.assertRedirects(res, reverse("directory:my_businesses"), fetch_redirect_response=False)
        business = Business.objects.get()
        self.assertEqual(business.owner, self.user)
        self.assertEqual(business.status, Business.Status.PENDING)
        self.assertEqual(business.location.coords, (-80.3553, 25.8195))

    def test_create_saves_offerings_as_embedded_array(self):
        self.post()
        business = Business.objects.get()
        self.assertEqual([o.name for o in business.offerings], ["Guitar lessons", "Golfeados"])
        self.assertEqual(business.offerings[0].price_from, Decimal("35.00"))
        self.assertIsInstance(business.offerings[1].price_from, Decimal)
        self.assertEqual(business.offerings[0].price_note, "per hour")

    def test_blank_offering_rows_ignored(self):
        self.post(**{"offerings-2-price_from": "9.99"})
        self.assertEqual(len(Business.objects.get().offerings), 2)

    def test_create_updates_search_terms(self):
        self.post()
        self.assertIn("golfeado", Business.objects.get().search_terms)

    def test_create_rejects_bad_lat_lng(self):
        self.assertFieldError(self.post(lat="91"), "lat")
        self.assertFieldError(self.post(lng=""), "lng")

    def test_create_requires_one_offering(self):
        res = self.post(**{"offerings-0-name": "", "offerings-1-name": ""})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context["offerings"].non_form_errors())
        self.assertFalse(Business.objects.exists())

    def test_negative_price_rejected(self):
        res = self.post(**{"offerings-0-price_from": "-1"})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Business.objects.exists())

    def test_at_most_ten_offerings(self):
        data = form_data(self.category, **{"offerings-TOTAL_FORMS": "11"})
        for i in range(11):
            data[f"offerings-{i}-name"] = f"Service {i}"
        res = self.client.post(self.url, data)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Business.objects.exists())

    def test_website_must_be_http(self):
        self.assertFieldError(self.post(website="javascript:alert(1)"), "website")
        self.assertFieldError(self.post(website="ftp://example.com"), "website")

    def test_phone_characters(self):
        self.assertFieldError(self.post(phone="call me maybe"), "phone")

    def test_started_on_future_rejected(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        self.assertFieldError(self.post(started_on=tomorrow.isoformat()), "started_on")

    def test_instagram_at_prefix_stripped(self):
        self.post(instagram="  @andres.guitar ")
        self.assertEqual(Business.objects.get().instagram, "andres.guitar")

    def test_instagram_url_rejected(self):
        res = self.post(instagram="https://www.instagram.com/andres.guitar/")
        self.assertFieldError(res, "instagram")
        self.assertIn("Enter just your handle", str(res.context["form"].errors["instagram"]))

    def test_offers_delivery_saved(self):
        self.post(offers_delivery="on")
        self.assertTrue(Business.objects.get().offers_delivery)

    def test_cannot_set_status_via_post(self):
        self.post(status="approved", owner=str(self.other.pk), slug="custom", rating_sum="50", rating_count="10")
        business = Business.objects.get()
        self.assertEqual(business.status, Business.Status.PENDING)
        self.assertEqual(business.owner, self.user)
        self.assertEqual(business.slug, "andres-guitar-lessons")
        self.assertEqual((business.rating_sum, business.rating_count), (0, 0))

    def test_csrf_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        res = client.post(self.url, form_data(self.category))
        self.assertEqual(res.status_code, 403)
        self.assertFalse(Business.objects.exists())


class BusinessEditTests(VendorTestCase):
    def edit_url(self, business):
        return reverse("directory:business_edit", args=[business.slug])

    def test_edit_form_prefilled(self):
        business = self.make(offerings=[Offering(name="Cuatro lessons", price_from=Decimal("30"))])
        res = self.client.get(self.edit_url(business))
        self.assertContains(res, 'value="Cuatro lessons"')
        self.assertContains(res, 'value="25.8195"')

    def test_edit_rejected_shows_moderator_note(self):
        business = self.make(status=Business.Status.REJECTED, rejection_reason="Add a price.")
        self.assertContains(self.client.get(self.edit_url(business)), "Add a price.")

    def test_edit_other_users_business_404(self):
        business = self.make(owner=self.other)
        self.assertEqual(self.client.get(self.edit_url(business)).status_code, 404)
        res = self.client.post(self.edit_url(business), form_data(self.category, name="Hijacked"))
        self.assertEqual(res.status_code, 404)
        business.refresh_from_db()
        self.assertEqual(business.name, "Existing")

    def test_edit_rejected_returns_to_pending(self):
        business = self.make(status=Business.Status.REJECTED, rejection_reason="Add a price.")
        res = self.client.post(self.edit_url(business), form_data(self.category, name="Fixed"))
        self.assertRedirects(res, reverse("directory:my_businesses"), fetch_redirect_response=False)
        business.refresh_from_db()
        self.assertEqual(business.status, Business.Status.PENDING)
        self.assertEqual(business.name, "Fixed")
        self.assertEqual(business.slug, "existing")

    def test_edit_approved_stays_approved(self):
        business = self.make(status=Business.Status.APPROVED)
        self.client.post(self.edit_url(business), form_data(self.category, name="Renamed"))
        business.refresh_from_db()
        self.assertEqual(business.status, Business.Status.APPROVED)
        self.assertEqual(business.name, "Renamed")

    def test_edit_replaces_offerings(self):
        business = self.make()
        self.client.post(self.edit_url(business), form_data(self.category))
        business.refresh_from_db()
        self.assertEqual([o.name for o in business.offerings], ["Guitar lessons", "Golfeados"])
