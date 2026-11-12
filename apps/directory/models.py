import re
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.gis.db import models
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django_mongodb_backend.fields import ArrayField, EmbeddedModelArrayField
from django_mongodb_backend.managers import MongoManager
from django_mongodb_backend.models import EmbeddedModel
from django_mongodb_backend.queryset import MongoQuerySet

from .search import MAX_TERM_CHARS, normalize_terms

NAME_MAX_LENGTH = 120

instagram_handle_validator = RegexValidator(
    r"^[A-Za-z0-9._]{1,30}\Z",
    _("Enter an Instagram handle without @: letters, numbers, dots and underscores."),
)


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Offering(EmbeddedModel):
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=300, blank=True)
    price_from = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    price_note = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return self.name


class BusinessQuerySet(MongoQuerySet):
    def approved(self):
        return self.filter(status=Business.Status.APPROVED)


class Business(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending review")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Needs changes")

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="businesses")
    name = models.CharField(max_length=NAME_MAX_LENGTH)
    # Room for a collision suffix after a full-length name.
    slug = models.SlugField(max_length=NAME_MAX_LENGTH + 10, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="businesses")
    description = models.TextField(blank=True)
    # Stored as GeoJSON; the backend creates a 2dsphere index automatically.
    location = models.PointField(srid=4326)
    address = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    website = models.URLField(blank=True)
    instagram = models.CharField(
        max_length=30, blank=True, validators=[instagram_handle_validator], help_text=_("Handle only, without @.")
    )
    offers_delivery = models.BooleanField(default=False)
    started_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    rejection_reason = models.TextField(blank=True)
    offerings = EmbeddedModelArrayField(Offering, default=list, blank=True)
    search_terms = ArrayField(models.CharField(max_length=MAX_TERM_CHARS), default=list, blank=True, editable=False)
    rating_sum = models.PositiveIntegerField(default=0, editable=False)
    rating_count = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = MongoManager.from_queryset(BusinessQuerySet)()

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "businesses"

    def __str__(self):
        return self.name

    # Changed only through atomic deltas (apps.directory.ratings), never by save().
    RATING_FIELDS = ("rating_sum", "rating_count")

    def save(self, *args, **kwargs):
        if self._state.adding and not self.slug:
            self.slug = self._unique_slug()
        self.search_terms = normalize_terms(self._searchable_text())
        if not self._state.adding and kwargs.get("update_fields") is None:
            # A stale in-memory instance must not overwrite concurrent rating updates.
            kwargs["update_fields"] = [
                f.name for f in self._meta.concrete_fields if not f.primary_key and f.name not in self.RATING_FIELDS
            ]
        super().save(*args, **kwargs)

    def _searchable_text(self) -> str:
        parts = [self.name, self.category.name, self.description]
        for offering in self.offerings:
            parts += [offering.name, offering.description]
        return " ".join(parts)

    def _unique_slug(self) -> str:
        # Concurrent creates with the same name can still race; the unique
        # index then rejects the second insert rather than duplicating.
        base = slugify(self.name)[:NAME_MAX_LENGTH].strip("-") or "business"
        taken = set(Business.objects.filter(slug__startswith=base).values_list("slug", flat=True))
        slug, n = base, 2
        while slug in taken:
            slug, n = f"{base}-{n}", n + 1
        return slug

    @property
    def years_active(self) -> int | None:
        if not self.started_on:
            return None
        today = timezone.localdate()
        before_anniversary = (today.month, today.day) < (self.started_on.month, self.started_on.day)
        return max(0, today.year - self.started_on.year - before_anniversary)

    @property
    def website_url(self) -> str:
        """The website only if it's http(s), so a stored `javascript:` URL never becomes a link."""
        return self.website if urlsplit(self.website).scheme.lower() in ("http", "https") else ""

    @property
    def phone_href(self) -> str:
        return re.sub(r"[^\d+]", "", self.phone)

    @property
    def rating_avg(self) -> float | None:
        if not self.rating_count:
            return None
        return round(self.rating_sum / self.rating_count, 1)


class Review(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="reviews")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField(max_length=2000, blank=True)
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["business", "author"], name="one_review_per_author")]

    def __str__(self):
        return f"{self.rating}★ for {self.business_id}"

    @property
    def author_name(self) -> str:
        # Never the email: it's private (product.md).
        return self.author.first_name or _("Anonymous")
