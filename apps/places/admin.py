from django import forms
from django.contrib import admin

from apps.geo.forms import LatLngFieldsMixin

from .models import Place


class PlaceAdminForm(LatLngFieldsMixin, forms.ModelForm):
    class Meta:
        model = Place
        fields = ["name", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_initial_from(self.instance.location)

    def save(self, commit=True):
        self.instance.location = self.point
        return super().save(commit)


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    form = PlaceAdminForm
    list_display = ["name", "location", "created_at"]
    search_fields = ["name"]
