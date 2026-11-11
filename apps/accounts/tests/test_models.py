from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

User = get_user_model()


class UserModelTests(TestCase):
    def test_email_is_username_field(self):
        self.assertEqual(User.USERNAME_FIELD, "email")
        self.assertEqual(User.REQUIRED_FIELDS, [])

    def test_email_normalized_to_lowercase(self):
        user = User.objects.create_user(email="Ana@Example.COM", password="x-Strong-pass-1")
        self.assertEqual(user.email, "ana@example.com")

    def test_email_unique_case_insensitive(self):
        User.objects.create_user(email="a@x.com", password="x-Strong-pass-1")
        with self.assertRaises((IntegrityError, ValidationError)):
            User.objects.create_user(email="A@x.com", password="x-Strong-pass-1")

    def test_create_superuser_by_email(self):
        user = User.objects.create_superuser(email="admin@x.com", password="x-Strong-pass-1")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("x-Strong-pass-1"))
