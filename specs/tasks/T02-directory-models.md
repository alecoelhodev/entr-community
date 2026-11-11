# T02: Directory models + moderation admin

**Status:** in progress
**Depends on:** T01, T03
**User stories:** US-10

## Goal
`Category`, `Business` and the embedded `Offering` exist with migrations. Staff can manage categories and approve or reject listings in the admin.

## Context
- Domain model: [product.md](../product.md#domain-model). Follow it exactly. Ask before deviating.
- `apps/places/models.py` shows the PointField + `MongoManager` pattern.
- `apps/places/admin.py` (`PlaceAdminForm`) shows the lat/lng admin form needed because of the CSP. Extract that logic into a reusable mixin here; T07 is its next caller.
- `apps/directory/search.normalize_terms` comes from T03.
- `Business.owner` is a FK to `settings.AUTH_USER_MODEL`. Start only after T01 merges, so the first `directory` migration depends on the custom user model.

## Acceptance criteria
- `Business.save()` sets `search_terms = normalize_terms(name + category name + description + offering names and descriptions)`.
- `Business.objects.approved()` returns only `status="approved"`.
- `slug` is generated from `name` on create and is unique. A collision appends `-2`, `-3`, … The slug doesn't change when the name is edited.
- `years_active`:
  - `None` without `started_on`.
  - `0` for less than a year.
  - Exact on the anniversary date. Compute it with `date.today()` injected or patched in tests.
- `rating_avg` is `None` when `rating_count == 0`, otherwise `round(rating_sum / rating_count, 1)`.
- Admin:
  - `Category` has `prepopulated_fields` for the slug.
  - `Business` has list_display (name, category, owner, status, created_at), list_filter (status, category), search by name, and actions **Approve** and **Reject**. Reject sets the status. The reason is edited on the change form.
  - The change form uses lat/lng fields via the mixin. Offerings can be edited inline in the admin as the embedded array.
- `apps/places/admin.py` uses the new mixin too, with no behavior change.

## Tests to write first
`apps/geo/tests/test_forms.py` → `LatLngFieldsMixinTests`
- `test_initial_from_instance_point`: an instance with `Point(-80.35, 25.81)` → initial `lng=-80.35`, `lat=25.81`.
- `test_cleaned_point_order`: `lat=25.81`, `lng=-80.35` → `Point(-80.35, 25.81, srid=4326)`.
- `test_out_of_range_rejected`.

`apps/directory/tests/test_models.py` → `BusinessModelTests`
- `test_search_terms_include_offerings`: an offering "Golfeados" → `"golfeado"` in `search_terms`.
- `test_search_terms_refresh_on_save`.
- `test_approved_queryset_excludes_pending_and_rejected`.
- `test_slug_generated_and_unique`, `test_slug_stable_on_rename`.
- `test_years_active_none_zero_and_anniversary`.
- `test_rating_avg`.
- `test_instagram_handle_validation`: `"la_casa.golfeado"` is valid. A leading `@` is rejected by the model validator, because stripping happens in the T07 form. A URL, spaces and 31+ characters are invalid.
- `test_offers_delivery_defaults_false`.
- `test_offerings_round_trip`: save and reload; `price_from` is a `Decimal`.
- `test_location_has_2dsphere_index`: inspect the collection's indexes, as `apps/geo/tests/test_queries.py` does if applicable.

`apps/directory/tests/test_admin.py` → `ModerationAdminTests`
- `test_approve_action_sets_status`, `test_reject_action_sets_status`.
- `test_changelist_requires_staff`.

## Implementation notes
- `Offering` is an `EmbeddedModel`, held in `django_mongodb_backend.fields.EmbeddedModelArrayField`. `search_terms` is `django_mongodb_backend.fields.ArrayField(models.CharField(max_length=40), default=list, blank=True)`, and is not editable in forms.
- Mixin location: `apps/geo/forms.py` → `LatLngFieldsMixin`, which declares `lat`/`lng` FloatFields and has `point` and `set_initial_from(point)` helpers. Keep it small.
- Admin inline editing of embedded arrays: check what the backend's admin supports in the pinned version. If inline editing isn't supported, use a formset on the change form, or keep offerings read-only in the admin for now and note it in the PR.
- `price_from`: `DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])`.

## Out of scope
- Public views (T04, T06).
- Vendor-facing forms (T07).
- `Review` model (T08).

## Manual verification
- In `/admin/`, create a category and a business with two offerings, approve it, and reload.
- Confirm the slug, `search_terms` (visible read-only) and status.
