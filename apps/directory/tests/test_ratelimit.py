from django.core.cache import cache
from django.urls import reverse

from .test_reviews import ReviewTestCase


class DirectoryRateLimitTestCase(ReviewTestCase):
    def setUp(self):
        cache.clear()


class ReviewRateLimitTests(DirectoryRateLimitTestCase):
    def test_review_user_limit(self):
        self.client.force_login(self.alice)
        url = self.url("review_update")  # No review yet: each POST 404s but still counts.
        for _ in range(20):
            self.assertEqual(self.client.post(url, {"rating": "3"}).status_code, 404)
        self.assertEqual(self.client.post(url, {"rating": "3"}).status_code, 429)
        self.client.force_login(self.bob)
        self.assertEqual(self.client.post(url, {"rating": "3"}).status_code, 404)

    def test_anonymous_redirected_not_counted(self):
        for _ in range(25):
            self.assertEqual(self.client.post(self.url("review_create"), {"rating": "3"}).status_code, 302)


class ListingRateLimitTests(DirectoryRateLimitTestCase):
    def test_business_create_user_limit(self):
        url = reverse("directory:business_create")
        self.client.force_login(self.alice)
        for _ in range(10):
            self.assertEqual(self.client.post(url, {}).status_code, 200)
        self.assertEqual(self.client.post(url, {}).status_code, 429)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.bob)
        self.assertEqual(self.client.post(url, {}).status_code, 200)
