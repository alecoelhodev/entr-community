from django import forms
from django.contrib import admin
from django.contrib.gis.geos import Point

from .models import Place


class PlaceAdminForm(forms.ModelForm):
    # Django's OSM admin widget loads OpenLayers from a CDN, which our CSP
    # blocks; plain lat/lng inputs keep the admin dependency-free.
    lat = forms.FloatField(min_value=-90, max_value=90)
    lng = forms.FloatField(min_value=-180, max_value=180)

    class Meta:
        model = Place
        fields = ["name", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.location:
            self.initial["lng"], self.initial["lat"] = self.instance.location.coords

    def save(self, commit=True):
        self.instance.location = Point(self.cleaned_data["lng"], self.cleaned_data["lat"], srid=4326)
        return super().save(commit)


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    form = PlaceAdminForm
    list_display = ["name", "location", "created_at"]
    search_fields = ["name"]
