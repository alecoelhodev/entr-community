from django.test import TestCase

from apps.directory.forms import BusinessFilterForm
from apps.directory.models import Category


class BusinessFilterFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bakery = Category.objects.create(name="Bakery", slug="bakery")

    def test_unknown_category_invalid(self):
        form = BusinessFilterForm({"category": "nope"})
        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_q_too_long_invalid(self):
        form = BusinessFilterForm({"q": "x" * 101})
        self.assertFalse(form.is_valid())
        self.assertIn("q", form.errors)

    def test_blank_filters_valid(self):
        form = BusinessFilterForm({"category": "", "q": "  "})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["category"])
        self.assertEqual(form.terms, [])

    def test_valid_category_and_terms(self):
        form = BusinessFilterForm({"category": "bakery", "q": "Golfeados de queso"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["category"], self.bakery)
        self.assertEqual(form.terms, ["golfeado", "queso"])
