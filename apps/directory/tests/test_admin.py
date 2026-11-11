from django.contrib.admin import helpers
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse, reverse_lazy

from apps.directory.models import Business, Category

User = get_user_model()


class ModerationAdminTests(TestCase):
    changelist = reverse_lazy("admin:directory_business_changelist")

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_superuser(email="staff@example.com", password="x")
        cls.owner = User.objects.create_user(email="owner@example.com", password="x")
        cls.category = Category.objects.create(name="Bakery", slug="bakery")
        cls.business = Business.objects.create(
            owner=cls.owner, category=cls.category, name="Panadería", location=Point(-80.35, 25.81, srid=4326)
        )

    def run_action(self, action):
        self.client.force_login(self.staff)
        return self.client.post(
            self.changelist, {"action": action, helpers.ACTION_CHECKBOX_NAME: [str(self.business.pk)]}
        )

    def test_approve_action_sets_status(self):
        Business.objects.filter(pk=self.business.pk).update(rejection_reason="Missing prices")
        res = self.run_action("approve")
        self.assertEqual(res.status_code, 302)
        self.business.refresh_from_db()
        self.assertEqual(self.business.status, Business.Status.APPROVED)
        self.assertEqual(self.business.rejection_reason, "")

    def test_reject_action_sets_status(self):
        res = self.run_action("reject")
        self.assertEqual(res.status_code, 302)
        self.business.refresh_from_db()
        self.assertEqual(self.business.status, Business.Status.REJECTED)

    def test_changelist_requires_staff(self):
        self.client.force_login(self.owner)
        res = self.client.get(self.changelist)
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse("admin:login"), res["Location"])

    def test_change_form_renders_lat_lng_and_offerings(self):
        self.client.force_login(self.staff)
        res = self.client.get(reverse("admin:directory_business_change", args=[self.business.pk]))
        self.assertContains(res, 'name="lat"')
        self.assertContains(res, 'value="25.81"')
        self.assertContains(res, 'name="offerings-0-name"')
