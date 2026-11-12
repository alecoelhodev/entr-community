from django.contrib.admin import helpers
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse

from apps.directory.models import Business, Category, Offering, Review
from apps.directory.ratings import apply_rating_delta

User = get_user_model()
DORAL = Point(-80.3553, 25.8195, srid=4326)


class ReviewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(email="owner@example.com", password="x", first_name="Carla")
        cls.alice = User.objects.create_user(email="alice@example.com", password="x", first_name="Alice")
        cls.bob = User.objects.create_user(email="bob@example.com", password="x")
        cls.staff = User.objects.create_superuser(email="staff@example.com", password="x")
        category = Category.objects.create(name="Bakery", slug="bakery")
        cls.business = Business.objects.create(
            owner=cls.owner, category=category, name="La Casa del Golfeado", status=Business.Status.APPROVED,
            location=DORAL, offerings=[Offering(name="Golfeados")],
        )
        cls.pending = Business.objects.create(
            owner=cls.owner, category=category, name="Pending Place", location=DORAL,
        )

    def url(self, name, business=None):
        return reverse(f"directory:{name}", args=[(business or self.business).slug])

    def aggregate(self):
        return tuple(Business.objects.filter(pk=self.business.pk).values_list("rating_sum", "rating_count").get())

    def post_review(self, user, rating=5, text="Great golfeados", business=None):
        self.client.force_login(user)
        return self.client.post(self.url("review_create", business), {"rating": str(rating), "text": text})


class ReviewAggregateTests(ReviewTestCase):
    def test_create_increments_sum_and_count(self):
        res = self.post_review(self.alice, 5)
        self.assertRedirects(res, self.url("detail"), fetch_redirect_response=False)
        self.post_review(self.bob, 3)
        self.assertEqual(self.aggregate(), (8, 2))
        self.assertEqual(Review.objects.count(), 2)

    def test_edit_applies_delta(self):
        self.post_review(self.alice, 5)
        res = self.client.post(self.url("review_update"), {"rating": "3", "text": "Changed my mind"})
        self.assertRedirects(res, self.url("detail"), fetch_redirect_response=False)
        self.assertEqual(self.aggregate(), (3, 1))
        self.assertEqual(Review.objects.get().text, "Changed my mind")

    def test_delete_decrements(self):
        self.post_review(self.alice, 4)
        self.post_review(self.bob, 2)
        res = self.client.post(self.url("review_delete"))
        self.assertRedirects(res, self.url("detail"), fetch_redirect_response=False)
        self.assertEqual(self.aggregate(), (4, 1))
        self.assertFalse(Review.objects.filter(author=self.bob).exists())

    def test_hide_and_unhide_adjust_aggregate(self):
        self.post_review(self.alice, 4)
        self.post_review(self.bob, 2)
        review = Review.objects.get(author=self.bob)
        self.run_admin_action("hide", review)
        self.assertEqual(self.aggregate(), (4, 1))
        self.run_admin_action("unhide", review)
        self.assertEqual(self.aggregate(), (6, 2))

    def test_hide_action_idempotent(self):
        self.post_review(self.alice, 4)
        review = Review.objects.get()
        self.run_admin_action("hide", review)
        self.run_admin_action("hide", review)
        self.assertEqual(self.aggregate(), (0, 0))
        self.run_admin_action("unhide", review)
        self.run_admin_action("unhide", review)
        self.assertEqual(self.aggregate(), (4, 1))

    def test_edit_hidden_review_does_not_touch_aggregate(self):
        self.post_review(self.alice, 5)
        self.run_admin_action("hide", Review.objects.get())
        self.client.force_login(self.alice)
        self.client.post(self.url("review_update"), {"rating": "1", "text": ""})
        self.assertEqual(self.aggregate(), (0, 0))

    def test_delete_hidden_review_does_not_touch_aggregate(self):
        self.post_review(self.alice, 5)
        self.run_admin_action("hide", Review.objects.get())
        self.client.force_login(self.alice)
        self.client.post(self.url("review_delete"))
        self.assertEqual(self.aggregate(), (0, 0))

    def test_aggregate_uses_atomic_update(self):
        stale = Business.objects.get(pk=self.business.pk)
        Business.objects.filter(pk=self.business.pk).update(rating_sum=10, rating_count=2)
        self.assertEqual((stale.rating_sum, stale.rating_count), (0, 0))
        apply_rating_delta(stale.pk, 4, 1)
        self.assertEqual(self.aggregate(), (14, 3))
        self.post_review(self.alice, 5)
        self.assertEqual(self.aggregate(), (19, 4))

    def test_business_save_does_not_overwrite_rating(self):
        stale = Business.objects.get(pk=self.business.pk)
        apply_rating_delta(self.business.pk, 5, 1)
        stale.description = "Vendor edit with a stale instance"
        stale.save()
        self.assertEqual(self.aggregate(), (5, 1))
        self.assertEqual(Business.objects.get(pk=self.business.pk).description, "Vendor edit with a stale instance")

    def test_deleting_user_removes_their_rating(self):
        self.post_review(self.alice, 4)
        self.post_review(self.bob, 2)
        self.bob.delete()
        self.assertEqual(self.aggregate(), (4, 1))

    def run_admin_action(self, action, review):
        self.client.force_login(self.staff)
        res = self.client.post(
            reverse("admin:directory_review_changelist"),
            {"action": action, helpers.ACTION_CHECKBOX_NAME: [str(review.pk)]},
        )
        self.assertEqual(res.status_code, 302)


class ReviewViewTests(ReviewTestCase):
    def test_anonymous_redirected_to_login(self):
        res = self.client.post(self.url("review_create"), {"rating": "5"})
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse("accounts:login"), res["Location"])
        self.assertFalse(Review.objects.exists())

    def test_anonymous_sees_login_prompt(self):
        res = self.client.get(self.url("detail"))
        self.assertContains(res, "Log in to write a review")
        self.assertNotContains(res, 'name="rating"')

    def test_owner_cannot_review_403(self):
        self.assertEqual(self.post_review(self.owner).status_code, 403)
        self.assertFalse(Review.objects.exists())
        self.assertNotContains(self.client.get(self.url("detail")), 'name="rating"')

    def test_pending_business_404(self):
        self.assertEqual(self.post_review(self.alice, business=self.pending).status_code, 404)

    def test_second_review_rejected_gracefully(self):
        self.post_review(self.alice, 5)
        res = self.post_review(self.alice, 1)
        self.assertIn(res.status_code, (200, 400))
        self.assertContains(res, "You already reviewed this business", status_code=res.status_code)
        self.assertEqual(self.aggregate(), (5, 1))

    def test_rating_out_of_range_400(self):
        for rating in (0, 6, "x"):
            with self.subTest(rating=rating):
                self.assertEqual(self.post_review(self.alice, rating).status_code, 400)
        self.assertFalse(Review.objects.exists())

    def test_text_too_long_400(self):
        self.assertEqual(self.post_review(self.alice, 4, "x" * 2001).status_code, 400)

    def test_update_or_delete_without_review_404(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.post(self.url("review_update"), {"rating": "3"}).status_code, 404)
        self.assertEqual(self.client.post(self.url("review_delete")).status_code, 404)

    def test_form_shown_to_logged_in_non_owner(self):
        self.client.force_login(self.alice)
        res = self.client.get(self.url("detail"))
        self.assertContains(res, "Write a review")
        self.assertContains(res, f'action="{self.url("review_create")}"')

    def test_own_review_shown_with_edit_and_delete(self):
        self.post_review(self.alice, 4, "Lovely")
        res = self.client.get(self.url("detail"))
        self.assertContains(res, f'action="{self.url("review_update")}"')
        self.assertContains(res, f'action="{self.url("review_delete")}"')
        self.assertNotContains(res, "Write a review")

    def test_list_shows_name_rating_and_newest_first(self):
        self.post_review(self.alice, 5, "First")
        self.post_review(self.bob, 3, "Second")
        self.client.logout()
        res = self.client.get(self.url("detail"))
        html = res.content.decode()
        self.assertLess(html.index("Second"), html.index("First"))
        self.assertContains(res, "Alice")
        self.assertContains(res, "Anonymous")
        self.assertContains(res, 'aria-label="5 out of 5 stars"')
        self.assertContains(res, "4.0 average · 2 reviews")

    def test_list_capped_at_20(self):
        for i in range(21):
            user = User.objects.create_user(email=f"u{i}@example.com", password="x")
            Review.objects.create(business=self.business, author=user, rating=4)
        res = self.client.get(self.url("detail"))
        self.assertEqual(len(res.context["reviews"]), 20)

    def test_hidden_reviews_not_listed(self):
        Review.objects.create(business=self.business, author=self.bob, rating=1, text="Spam spam", is_hidden=True)
        self.assertNotContains(self.client.get(self.url("detail")), "Spam spam")

    def test_review_text_escaped(self):
        self.post_review(self.alice, 4, "<script>alert(1)</script>")
        self.client.logout()
        res = self.client.get(self.url("detail"))
        self.assertNotContains(res, "<script>alert(1)</script>")
        self.assertContains(res, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_author_email_never_rendered(self):
        self.post_review(self.bob, 4, "No name set")
        self.client.logout()
        self.assertNotContains(self.client.get(self.url("detail")), "bob@example.com")

    def test_get_not_allowed_on_mutations(self):
        self.client.force_login(self.alice)
        for name in ("review_create", "review_update", "review_delete"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(self.url(name)).status_code, 405)

    def test_panel_has_no_review_form(self):
        self.client.force_login(self.alice)
        self.assertNotContains(self.client.get(self.url("panel")), 'name="rating"')


class ReviewAdminTests(ReviewTestCase):
    def test_changelist_filters_and_actions(self):
        Review.objects.create(business=self.business, author=self.alice, rating=4)
        self.client.force_login(self.staff)
        res = self.client.get(reverse("admin:directory_review_changelist"))
        self.assertContains(res, 'value="hide"')
        self.assertContains(res, 'value="unhide"')
        self.assertContains(res, "is_hidden")

    def test_admin_cannot_add_or_edit_rating(self):
        review = Review.objects.create(business=self.business, author=self.alice, rating=4)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("admin:directory_review_add")).status_code, 403)
        res = self.client.get(reverse("admin:directory_review_change", args=[review.pk]))
        self.assertNotContains(res, 'name="rating"')
        self.assertNotContains(res, 'name="is_hidden"')
