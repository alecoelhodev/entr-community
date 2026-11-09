from django.test import SimpleTestCase

from apps.geo.forms import MAX_RADIUS_KM, BBoxForm, NearbyQueryForm


class NearbyQueryFormTests(SimpleTestCase):
    def test_valid_edges_and_point_order(self):
        form = NearbyQueryForm({"lat": "90", "lng": "-180", "radius_km": str(MAX_RADIUS_KM)})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.point.coords, (-180.0, 90.0))

    def test_default_radius(self):
        form = NearbyQueryForm({"lat": "1", "lng": "1"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["radius_km"], 5.0)

    def test_out_of_range(self):
        for data in (
            {"lat": "90.1", "lng": "0"},
            {"lat": "0", "lng": "180.1"},
            {"lat": "0", "lng": "0", "radius_km": str(MAX_RADIUS_KM + 1)},
            {"lat": "nan", "lng": "0"},
        ):
            with self.subTest(data=data):
                self.assertFalse(NearbyQueryForm(data).is_valid())


class BBoxFormTests(SimpleTestCase):
    def test_valid(self):
        form = BBoxForm({"bbox": "-9.2,38.7,-9.1,38.8"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["bbox"].extent, (-9.2, 38.7, -9.1, 38.8))

    def test_invalid(self):
        for bbox in ("1,2,3", "a,b,c,d", "10,0,5,1", "0,0,1,91", "0,0,10,1"):
            with self.subTest(bbox=bbox):
                self.assertFalse(BBoxForm({"bbox": bbox}).is_valid())
