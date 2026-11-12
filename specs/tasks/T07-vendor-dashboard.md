# T07: Vendor dashboard: create and edit listings

**Status:** in progress
**Depends on:** T01, T02
**User stories:** US-7, US-8, US-9

## Goal
A logged-in user can list their businesses with moderation status, create a new listing (which starts `pending`) and edit their own listings, including services and prices. They pick the location on a map.

## Context
- `Business`, `Offering` and `LatLngFieldsMixin` come from T02. The `User` model comes from T01.
- Moderation rules are in [product.md](../product.md#rules).
- Map pattern: `static/js/map.js`. The CSP rules from CLAUDE.md apply.

## Acceptance criteria
- `/me/businesses/` (`directory:my_businesses`), login required:
  - Lists the user's businesses with name, category and a status badge.
  - Shows the rejection reason for rejected listings.
  - Has links to edit each listing and to create a new one.
- `/me/businesses/new/` and `/me/businesses/<slug>/edit/`, login required:
  - Fields: name, category, description, started_on, an `offers_delivery` checkbox, location (map picker writing hidden `lat`/`lng`), address, phone, website, Instagram handle (with a fixed `@` prefix in the UI), and offerings (up to 10 rows).
  - The layout follows the `Dashboard` and `ListingForm` artboards in [design.md](../design.md). A rejected listing's status reads "Needs changes".
  - **Create:** `owner = request.user`, `status = pending`, redirect to the dashboard with a success message.
  - **Edit:** only the owner may edit. Anyone else gets a **404** (no existence leak); staff use the admin. A rejected listing goes back to `pending` on save. An approved listing stays approved.
  - The owner can't set `status`, `owner`, `slug`, `search_terms` or the rating fields. They aren't form fields.
- Validation:
  - `website` must be `http`/`https`.
  - `instagram`: trim whitespace, strip one leading `@`, then apply the model validator. A pasted profile URL is rejected with "Enter just your handle".
  - Phone is ≤ 30 characters, digits and `+()- ` only.
  - `started_on` is not in the future.
  - `price_from` ≥ 0.
  - Offering rows with a blank name are ignored.
  - At least 1 offering is required.
- Every state change is POST + CSRF.

## Tests to write first
`apps/directory/tests/test_vendor_views.py` → `VendorDashboardTests`, `BusinessCreateTests`, `BusinessEditTests`
- `test_dashboard_requires_login`: redirect to login.
- `test_dashboard_lists_only_own_businesses_with_status`.
- `test_create_sets_owner_and_pending`.
- `test_create_saves_offerings_as_embedded_array`: reload; two offerings with Decimal prices.
- `test_create_updates_search_terms`: an offering "Golfeados" makes it findable via `search_terms`.
- `test_create_rejects_bad_lat_lng`.
- `test_create_requires_one_offering`.
- `test_website_must_be_http`: `javascript:` → error.
- `test_started_on_future_rejected`.
- `test_instagram_at_prefix_stripped`: `"@andres.guitar"` is stored as `andres.guitar`.
- `test_instagram_url_rejected`.
- `test_offers_delivery_saved`.
- `test_cannot_set_status_via_post`: posting `status=approved` is ignored.
- `test_edit_other_users_business_404`.
- `test_edit_rejected_returns_to_pending`.
- `test_edit_approved_stays_approved`.
- `test_csrf_enforced`: use `Client(enforce_csrf_checks=True)`.

## Implementation notes
- `BusinessForm(LatLngFieldsMixin, forms.ModelForm)` plus an `OfferingFormSet = formset_factory(OfferingForm, extra=…, max_num=10)`.
  - Build the `Offering` instances from `cleaned_data` and assign them to `business.offerings` before `save()`.
  - Fixed extra rows are fine. Adding rows dynamically would need an `Alpine.data` component in a static file; that's optional.
- Location picker: `static/js/location-picker.js` registers `Alpine.data("locationPicker")`:
  - Shows a Leaflet map centered on the current value or the Doral default.
  - On click, it moves a marker and writes the hidden `lat`/`lng` inputs (via `x-ref`).
  - Load it only on these pages (`{% block scripts %}`).
- Ownership: `get_object_or_404(Business, slug=slug, owner=request.user)`.
- Set the `status` transition in the view, not the form.

## Out of scope
- Deleting listings (staff via the admin for now).
- Photos.
- Re-moderation of approved edits (open question in product.md).

## Manual verification
1. Sign up and create a listing by clicking the map. It shows `pending` in the dashboard.
2. Approve it in the admin. It appears on the public map.
3. Reject another listing with a reason, edit it, and see it back at `pending`.
