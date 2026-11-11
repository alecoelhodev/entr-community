from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _, ngettext

from apps.geo.forms import LatLngFieldsMixin

from .models import Business, Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}


class BusinessAdminForm(LatLngFieldsMixin, forms.ModelForm):
    class Meta:
        model = Business
        exclude = ["location"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_initial_from(self.instance.location)

    def save(self, commit=True):
        self.instance.location = self.point
        return super().save(commit)


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    form = BusinessAdminForm
    list_display = ["name", "category", "owner", "status", "created_at"]
    list_filter = ["status", "category"]
    search_fields = ["name"]
    actions = ["approve", "reject"]
    readonly_fields = ["slug", "search_terms", "rating_sum", "rating_count", "created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["name", "slug", "owner", "category", "description"]}),
        (_("Moderation"), {"fields": ["status", "rejection_reason"]}),
        (_("Location"), {"fields": ["lat", "lng", "address"]}),
        (_("Contact"), {"fields": ["phone", "website", "instagram", "offers_delivery", "started_on"]}),
        (_("Offerings"), {"fields": ["offerings"]}),
        (_("Derived"), {"fields": ["search_terms", "rating_sum", "rating_count", "created_at", "updated_at"]}),
    ]

    @admin.action(description=_("Approve selected businesses"))
    def approve(self, request, queryset):
        count = queryset.update(status=Business.Status.APPROVED, rejection_reason="")
        self.message_user(request, ngettext("%d business approved.", "%d businesses approved.", count) % count)

    @admin.action(description=_("Reject selected businesses (add the reason on each one)"))
    def reject(self, request, queryset):
        count = queryset.update(status=Business.Status.REJECTED)
        self.message_user(request, ngettext("%d business rejected.", "%d businesses rejected.", count) % count)
