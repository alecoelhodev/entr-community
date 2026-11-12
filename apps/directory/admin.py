from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _, ngettext
from django_mongodb_backend.transaction import atomic

from apps.geo.forms import LatLngFieldsMixin

from .models import Business, Category, Review
from .ratings import apply_rating_delta


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


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["business", "author", "rating", "is_hidden", "created_at"]
    list_filter = ["is_hidden", "rating"]
    search_fields = ["text"]
    actions = ["hide", "unhide"]
    # Read-only: rating and visibility change only through the actions, which keep the aggregate right.
    readonly_fields = ["business", "author", "rating", "text", "is_hidden", "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False

    @admin.action(description=_("Hide selected reviews"))
    def hide(self, request, queryset):
        count = self._set_hidden(queryset, hidden=True)
        self.message_user(request, ngettext("%d review hidden.", "%d reviews hidden.", count) % count)

    @admin.action(description=_("Unhide selected reviews"))
    def unhide(self, request, queryset):
        count = self._set_hidden(queryset, hidden=False)
        self.message_user(request, ngettext("%d review unhidden.", "%d reviews unhidden.", count) % count)

    def _set_hidden(self, queryset, hidden: bool) -> int:
        changed = 0
        for pk in queryset.filter(is_hidden=not hidden).values_list("pk", flat=True):
            with atomic():
                # Conditional update: only the request that flips the flag applies the delta.
                review = Review.objects.filter(pk=pk, is_hidden=not hidden).first()
                if review and Review.objects.filter(pk=pk, is_hidden=not hidden).update(is_hidden=hidden):
                    sign = -1 if hidden else 1
                    apply_rating_delta(review.business_id, sign * review.rating, sign)
                    changed += 1
        return changed
