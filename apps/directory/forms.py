import re
from urllib.parse import urlsplit

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from apps.geo.forms import LatLngFieldsMixin

from .models import Business, Category, Offering
from .search import query_terms


class BusinessFilterForm(forms.Form):
    """Optional map filters shared by the GeoJSON and nearby endpoints."""

    category = forms.ModelChoiceField(queryset=Category.objects.all(), to_field_name="slug", required=False)
    q = forms.CharField(max_length=100, required=False)

    @cached_property
    def terms(self) -> list[str]:
        return query_terms(self.cleaned_data["q"])


PHONE_RE = re.compile(r"^[\d+()\- ]*\Z")
MAX_OFFERINGS = 10


class BusinessForm(LatLngFieldsMixin, forms.ModelForm):
    """Vendor-editable fields. Status, owner, slug and derived fields are set by the view/model."""

    # Longer than the model's 30 so a pasted profile URL reaches clean_instagram's
    # clearer message; the model validator still enforces the handle format and length.
    instagram = forms.CharField(
        max_length=200,
        required=False,
        help_text=_("Just your handle, without the link."),
        widget=forms.TextInput(attrs={"autocomplete": "off", "autocapitalize": "none"}),
    )

    class Meta:
        model = Business
        fields = [
            "name", "category", "description", "started_on", "offers_delivery",
            "address", "phone", "website", "instagram",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "started_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "phone": forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}),
            "website": forms.URLInput(attrs={"placeholder": "https://"}),
            "address": forms.TextInput(attrs={"placeholder": _("Street, suite, Doral, FL")}),
        }
        labels = {
            "name": _("Business name"),
            "started_on": _("In business since"),
            "offers_delivery": _("I offer delivery"),
            "address": _("Address shown to customers (optional)"),
        }
        help_texts = {
            "offers_delivery": _("Your listing shows a “Delivery” badge on the map and your page."),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_initial_from(self.instance.location)
        for name in ("lat", "lng"):
            self.fields[name].widget.attrs.update({"x-ref": name, "step": "any", "@change": "syncFromInputs"})
            self.fields[name].error_messages["required"] = _("Click the map to place your business.")
        self.fields["lat"].label = _("Latitude")
        self.fields["lng"].label = _("Longitude")

    def clean_website(self):
        website = self.cleaned_data["website"]
        if website and urlsplit(website).scheme.lower() not in ("http", "https"):
            raise ValidationError(_("Use a link that starts with http:// or https://"))
        return website

    def clean_instagram(self):
        handle = self.cleaned_data["instagram"].strip()
        if "/" in handle or "instagram.com" in handle.lower():
            raise ValidationError(_("Enter just your handle, not a link."))
        return handle.removeprefix("@")

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if not PHONE_RE.match(phone):
            raise ValidationError(_("Use only digits, spaces and + ( ) -"))
        return phone

    def clean_started_on(self):
        started_on = self.cleaned_data["started_on"]
        if started_on and started_on > timezone.localdate():
            raise ValidationError(_("This date can't be in the future."))
        return started_on

    def save(self, commit=True):
        self.instance.location = self.point
        return super().save(commit)


class OfferingForm(forms.Form):
    # Not required: rows with a blank name are ignored rather than rejected.
    name = forms.CharField(label=_("Name"), max_length=80, required=False)
    price_from = forms.DecimalField(
        label=_("Price from ($)"), max_digits=8, decimal_places=2, min_value=0, required=False
    )
    price_note = forms.CharField(label=_("Price note"), max_length=80, required=False)
    description = forms.CharField(label=_("Short description (optional)"), max_length=300, required=False)


class BaseOfferingFormSet(forms.BaseFormSet):
    def clean(self):
        super().clean()
        if not any(self.errors) and not self.offerings():
            raise ValidationError(_("Add at least one product or service."))

    def offerings(self) -> list[Offering]:
        return [Offering(**form.cleaned_data) for form in self.forms if form.cleaned_data.get("name")]


OfferingFormSet = forms.formset_factory(
    OfferingForm,
    formset=BaseOfferingFormSet,
    extra=3,
    max_num=MAX_OFFERINGS,
    absolute_max=MAX_OFFERINGS,
    validate_max=True,
)
