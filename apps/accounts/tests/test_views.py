from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import TestCase
from django.urls import reverse, reverse_lazy

User = get_user_model()
PASSWORD = "x-Strong-pass-1"


def signup_data(**overrides):
    data = {
        "first_name": "Ana",
        "email": "ana@example.com",
        "password1": PASSWORD,
        "password2": PASSWORD,
    }
    data.update(overrides)
    return data


class SignupViewTests(TestCase):
    url = reverse_lazy("accounts:signup")

    def test_signup_page_renders(self):
        res = self.client.get(self.url)
        self.assertContains(res, "Create your account")

    def test_signup_creates_and_logs_in(self):
        res = self.client.post(self.url, signup_data())
        self.assertRedirects(res, "/", fetch_redirect_response=False)
        user = User.objects.get(email="ana@example.com")
        self.assertEqual(user.first_name, "Ana")
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))

    def test_signup_requires_first_name(self):
        res = self.client.post(self.url, signup_data(first_name=""))
        self.assertEqual(res.status_code, 200)
        self.assertIn("first_name", res.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_signup_duplicate_email_rejected(self):
        User.objects.create_user(email="ana@example.com", password=PASSWORD)
        res = self.client.post(self.url, signup_data(email="ANA@example.com"))
        self.assertEqual(res.status_code, 200)
        self.assertIn("email", res.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_signup_password_mismatch_rejected(self):
        res = self.client.post(self.url, signup_data(password2="something-else-9"))
        self.assertEqual(res.status_code, 200)
        self.assertIn("password2", res.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_pages_send_csp_header(self):
        for name in ("accounts:signup", "accounts:login"):
            with self.subTest(name=name):
                res = self.client.get(reverse(name))
                self.assertIn("Content-Security-Policy", res.headers)


class LoginLogoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="ana@example.com", password=PASSWORD, first_name="Ana"
        )

    def test_login_with_email(self):
        res = self.client.post(
            reverse("accounts:login"), {"username": "Ana@Example.com", "password": PASSWORD}
        )
        self.assertRedirects(res, "/", fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))

    def test_login_wrong_password_generic_error(self):
        url = reverse("accounts:login")
        wrong_pw = self.client.post(url, {"username": "ana@example.com", "password": "nope-nope-1"})
        no_user = self.client.post(url, {"username": "nobody@example.com", "password": "nope-nope-1"})
        self.assertEqual(wrong_pw.status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(
            wrong_pw.context["form"].non_field_errors(), no_user.context["form"].non_field_errors()
        )
        self.assertTrue(wrong_pw.context["form"].non_field_errors())

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        url = reverse("accounts:logout")
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertIn(SESSION_KEY, self.client.session)
        res = self.client.post(url)
        self.assertEqual(res.status_code, 302)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_header_shows_login_links_when_anonymous(self):
        res = self.client.get("/")
        self.assertContains(res, f'href="{reverse("accounts:login")}"')
        self.assertContains(res, f'href="{reverse("accounts:signup")}"')
        self.assertNotContains(res, f'action="{reverse("accounts:logout")}"')

    def test_header_shows_name_when_authenticated(self):
        self.client.force_login(self.user)
        res = self.client.get("/")
        self.assertContains(res, "Ana")
        self.assertContains(res, f'action="{reverse("accounts:logout")}"')
        self.assertNotContains(res, f'href="{reverse("accounts:login")}"')
