from django import forms
from django.utils.functional import cached_property

from .models import Category
from .search import query_terms


class BusinessFilterForm(forms.Form):
    """Optional map filters shared by the GeoJSON and nearby endpoints."""

    category = forms.ModelChoiceField(queryset=Category.objects.all(), to_field_name="slug", required=False)
    q = forms.CharField(max_length=100, required=False)

    @cached_property
    def terms(self) -> list[str]:
        return query_terms(self.cleaned_data["q"])
