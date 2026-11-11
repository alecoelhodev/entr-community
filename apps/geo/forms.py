"""Boundary validation for geo query parameters (lat/lng as sent by Leaflet)."""

from django import forms
from django.contrib.gis.geos import Point, Polygon

MAX_RADIUS_KM = 50
# Rough cap on bbox size so one request can't scan the whole planet.
MAX_BBOX_SPAN_DEG = 5


class NearbyQueryForm(forms.Form):
    lat = forms.FloatField(min_value=-90, max_value=90)
    lng = forms.FloatField(min_value=-180, max_value=180)
    radius_km = forms.FloatField(min_value=0.01, max_value=MAX_RADIUS_KM, required=False)

    def clean_radius_km(self):
        return self.cleaned_data["radius_km"] or 5.0

    @property
    def point(self) -> Point:
        # GeoJSON/GEOS order is (lng, lat).
        return Point(self.cleaned_data["lng"], self.cleaned_data["lat"], srid=4326)


class BBoxForm(forms.Form):
    """Leaflet's `map.getBounds().toBBoxString()` → `west,south,east,north`."""

    bbox = forms.CharField()

    def clean_bbox(self):
        try:
            west, south, east, north = (float(v) for v in self.cleaned_data["bbox"].split(","))
        except ValueError:
            raise forms.ValidationError("Expected west,south,east,north.")
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise forms.ValidationError("Coordinates out of range or inverted.")
        if east - west > MAX_BBOX_SPAN_DEG or north - south > MAX_BBOX_SPAN_DEG:
            raise forms.ValidationError("Area too large; zoom in.")
        return Polygon.from_bbox((west, south, east, north))


class LatLngFieldsMixin(forms.Form):
    """Plain lat/lng inputs for a PointField.

    Django's OSM map widget loads OpenLayers from a CDN that our CSP blocks.
    Mix into a ModelForm: call ``set_initial_from(instance.location)`` in
    ``__init__`` and assign ``self.point`` to the field on save.
    """

    lat = forms.FloatField(min_value=-90, max_value=90)
    lng = forms.FloatField(min_value=-180, max_value=180)

    def set_initial_from(self, point: Point | None) -> None:
        if point:
            self.initial["lng"], self.initial["lat"] = point.coords

    @property
    def point(self) -> Point:
        return Point(self.cleaned_data["lng"], self.cleaned_data["lat"], srid=4326)
