from django.test import SimpleTestCase

from apps.directory.search import normalize_terms, query_terms


class NormalizeTermsTests(SimpleTestCase):
    def test_plural_spanish(self):
        self.assertEqual(normalize_terms("Golfeados"), ["golfeado"])
        self.assertEqual(normalize_terms("cachitos"), ["cachito"])

    def test_plural_english(self):
        self.assertEqual(normalize_terms("T-Shirt Printing"), ["shirt", "printing"])
        self.assertEqual(normalize_terms("printers"), ["printer"])
        self.assertEqual(normalize_terms("business"), ["business"])

    def test_short_tokens_not_singularized(self):
        self.assertEqual(normalize_terms("gas bus"), ["gas", "bus"])

    def test_accent_folding(self):
        self.assertEqual(normalize_terms("Café Piñata"), ["cafe", "pinata"])

    def test_stopwords_dropped(self):
        self.assertEqual(
            normalize_terms("clases de guitarra para niños"),
            ["clase", "guitarra", "nino"],
        )
        self.assertEqual(normalize_terms("the best bakery"), ["best", "bakery"])

    def test_empty_and_whitespace(self):
        for text in ("", "   ", "--"):
            with self.subTest(text=text):
                self.assertEqual(normalize_terms(text), [])

    def test_idempotent(self):
        samples = [
            "Golfeados y cachitos recién horneados",
            "T-Shirt Printing & Custom Embroidery",
            "Clases de guitarra para niños",
            "business classes glasses",
            "x" * 45 + "s",
        ]
        for text in samples:
            with self.subTest(text=text):
                once = normalize_terms(text)
                self.assertEqual(normalize_terms(" ".join(once)), once)

    def test_dedup_preserves_order(self):
        self.assertEqual(
            normalize_terms("cachitos golfeados Cachito golfeado"),
            ["cachito", "golfeado"],
        )

    def test_bounds(self):
        words = [f"w{i}" + "a" * 60 for i in range(5000)]
        terms = normalize_terms(" ".join(words) * 2)
        self.assertLessEqual(len(terms), 200)
        self.assertTrue(terms)
        self.assertTrue(all(len(t) <= 40 for t in terms))

    def test_input_truncated_before_processing(self):
        text = "a" * 10_000 + " cachito"
        self.assertNotIn("cachito", normalize_terms(text))


class QueryTermsTests(SimpleTestCase):
    def test_same_pipeline_as_normalize(self):
        for q in ("Golfeados", "T-Shirt Printing", "Café Piñata", "the best bakery"):
            with self.subTest(q=q):
                self.assertEqual(query_terms(q), normalize_terms(q))

    def test_caps_term_count(self):
        q = " ".join(f"word{i}" for i in range(20))
        self.assertEqual(query_terms(q), [f"word{i}" for i in range(8)])
