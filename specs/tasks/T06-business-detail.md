# T06: Business detail page + panel

**Status:** ready
**Depends on:** T02
**User stories:** US-4

## Goal
Anyone can open an approved business and see everything a customer needs to decide. A shareable full page shows it, and an HTMX partial shows the same content in the map sidebar.

## Context
- `Business` and its properties (`years_active`, `rating_avg`) come from T02.
- The `Review` model arrives in T08. This task renders only the rating summary from `rating_sum`/`rating_count`. T08 adds the review list and form to `_detail_body.html`.
- The template pattern is `templates/places/_nearby_list.html` for partials and `templates/base.html` for the layout.

## Acceptance criteria
- `GET /b/<slug>/` (`directory:detail`) renders the full page extending `base.html`.
- `GET /b/<slug>/panel/` (`directory:panel`) renders the same content as a partial with no layout.
- Content:
  - Name, category, description.
  - Address, phone (`tel:` link), website and Instagram, each only if set. External links use `rel="noopener nofollow ugc"` and `target="_blank"`. Instagram renders as `@handle`, linking to `https://www.instagram.com/<handle>/`.
  - An "Offers delivery" badge when `offers_delivery` is set.
  - The layout follows the `Panel` and `Detail` artboards in [design.md](../design.md).
  - "Active since YYYY · N years", or "N/A" if there's no `started_on`. Use singular/plural correctly.
  - Offerings: name, description, and "From $X.XX <note>", or "Ask for price" when `price_from` is empty.
  - Rating: "4.3 ★ (12 reviews)", or "No reviews yet".
- Visibility:
  - Approved → 200 for everyone.
  - Pending or rejected → 404 for anonymous users and other users; 200 for the owner and staff, with a visible status banner. The owner also sees the `rejection_reason`.
- Both views use `@require_safe`. Unknown slug → 404.
- All vendor-supplied text is auto-escaped. Never use `|safe` on vendor content. Validate the website URL scheme (`http`/`https` only) at the model or form level in T07. In this task, render it only if it starts with `http://` or `https://`.

## Tests to write first
`apps/directory/tests/test_detail.py` → `BusinessDetailTests`
- `test_approved_detail_200_shows_offerings_and_prices`: "From $12.00 per dozen".
- `test_offering_without_price_shows_ask_for_price`.
- `test_active_since_years`: patch today; covers 0, 1 and N years.
- `test_rating_summary`: "No reviews yet" at count 0; "4.3 ★ (12 reviews)" with sum 52, count 12.
- `test_pending_404_for_anonymous_and_other_user`.
- `test_pending_200_for_owner_with_status_banner`.
- `test_rejected_shows_reason_to_owner_only`.
- `test_staff_can_view_pending`.
- `test_panel_is_partial`: no `<html`.
- `test_vendor_text_escaped`: a description containing `<script>` is rendered escaped.
- `test_website_non_http_scheme_not_linked`: `javascript:alert(1)` is not rendered as a link.
- `test_unknown_slug_404`.
- `test_instagram_link_built_from_handle`: the href is exactly `https://www.instagram.com/<handle>/`; nothing renders when blank.
- `test_delivery_badge_only_when_offered`.

## Implementation notes
- Write one helper, `get_visible_business(request, slug)`, used by both views. It returns the business or raises `Http404`.
- Share the content between page and panel: `detail.html` includes `_detail_body.html`, and the panel renders `_detail_body.html` directly.
- Money formatting: `{{ offering.price_from|floatformat:2 }}`, prefixed with `$`. USD only in the MVP.

## Out of scope
- The reviews list and form (T08).
- Map integration (T05).
- Photos.

## Manual verification
Open an approved business, then a pending one (logged out and logged in as the owner).
