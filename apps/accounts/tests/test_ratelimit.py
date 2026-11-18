from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class RateLimitTestCase(TestCase):
    def setUp(self):
        cache.clear()

    def post_from(self, url, ip, data):
        return self.client.post(url, data, HTTP_X_FORWARDED_FOR=ip)

    def assertLimited(self, res):
        self.assertEqual(res.status_code, 429)
        self.assertContains(res, "Too many attempts", status_code=429)


class LoginRateLimitTests(RateLimitTestCase):
    url = reverse("accounts:login")

    def login(self, ip, email="someone@example.com"):
        return self.post_from(self.url, ip, {"username": email, "password": "wrong"})

    def test_login_ip_limit_returns_429(self):
        for i in range(10):
            self.assertEqual(self.login("203.0.113.5", f"user{i}@example.com").status_code, 200)
        res = self.login("203.0.113.5", "user10@example.com")
        self.assertLimited(res)
        self.assertNotContains(res, "user10@example.com", status_code=429)
        self.assertEqual(self.login("203.0.113.6", "other@example.com").status_code, 200)

    def test_login_email_limit_across_ips(self):
        for i in range(20):
            self.assertEqual(self.login(f"198.51.100.{i}", "Victim@Example.com").status_code, 200)
        self.assertLimited(self.login("198.51.100.200", "victim@example.com"))

    def test_get_never_limited(self):
        for _ in range(15):
            self.assertEqual(self.client.get(self.url, HTTP_X_FORWARDED_FOR="203.0.113.5").status_code, 200)


class SignupRateLimitTests(RateLimitTestCase):
    url = reverse("accounts:signup")

    def test_signup_ip_limit_returns_429(self):
        for _ in range(5):
            self.assertEqual(self.post_from(self.url, "203.0.113.7", {}).status_code, 200)
        self.assertLimited(self.post_from(self.url, "203.0.113.7", {}))
        self.assertEqual(self.post_from(self.url, "203.0.113.8", {}).status_code, 200)
