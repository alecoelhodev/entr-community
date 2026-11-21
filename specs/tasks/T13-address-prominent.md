# T13: Required, prominent business address

**Status:** in review
**Depends on:** — (MVP done)
**User stories:** US-14

## Goal
Customers always see where a business is. Vendors must give an address, and it's shown right under the business name in the map sidebar (result cards and panel) and on the full business page.

## Context
- Product decision (2026-11-15): the address becomes **required**, and is shown **prominently**.
- Today `Business.address` is `CharField(max_length=200, blank=True)`, labelled "Address shown to customers (optional)" in `BusinessForm` (`apps/directory/forms.py`).
- It appears only in the contact list at the bottom of `templates/directory/_detail_body.html` (panel and page), and only when set.
- The sidebar result cards (`templates/directory/_nearby_list.html`) don't show it.
- There's still no geocoding: the address is free text, and the map pin comes from the location picker.
- Existing listings may have a blank address. Requiring it at the model level would make their next save fail validation, which is the desired nudge. It must not break the public pages.

## Acceptance criteria
- **Form:** `BusinessForm` requires `address`, labelled "Address", with help text "Shown to customers, e.g. 8250 NW 36th St, Suite 4, Doral, FL". Blank or whitespace-only → "Enter the address customers should visit".
- **Model:** `address` becomes `blank=False`, at most 200 chars, stripped. The migration is metadata-only (no data change), and existing blank values are left as they are.
- **Panel and full page:** the address shows under the name and meta line, with the pin icon. The contact list keeps phone, website and Instagram, and drops the duplicate address row.
- **Sidebar result cards:** one muted line with the address, truncated with an ellipsis via CSS (never cut in the HTML), under the category/rating row.
- **Blank address on an existing listing:**
  - Public pages omit the line, with no empty element.
  - The vendor dashboard shows "Add your address so customers can find you" with a link to edit.
- **Admin:** the address is required on the change form too, since the model change drives it.
- **Seed data:** every `seed_directory` business already has, or gets, a fictional but plausible Doral address. Existing seeds are left as they are (the command skips existing slugs), so mention this in the PR.
- The address is vendor text, always auto-escaped and never `|safe`.

## Tests to write first
`apps/directory/tests/test_vendor_views.py` (extend)
- `test_create_requires_address`: blank → form error, no business created.
- `test_address_whitespace_only_rejected`.

`apps/directory/tests/test_detail.py` (extend)
- `test_address_shown_under_name_on_page_and_panel`: inside the header block, appearing once rather than also in the contact list.
- `test_blank_address_renders_no_empty_line`.
- `test_address_escaped`.

`apps/directory/tests/test_api.py` (extend `BusinessNearbyTests`)
- `test_result_card_shows_address`.

`apps/directory/tests/test_vendor_views.py` (extend `VendorDashboardTests`)
- `test_dashboard_prompts_for_missing_address`.

`apps/directory/tests/test_seed.py` (extend)
- `test_seeded_businesses_have_addresses`.

## Implementation notes
- Reuse the existing pin SVG from the contact list.
- In the address line, keep the icon decorative (`aria-hidden`) and give the text an `sr-only` "Address:" prefix. Add a `.sr-only` utility to `app.css` if it isn't there yet.
- Update `specs/design.md` (Components → Contact list and result cards) and `specs/product.md` (the domain model's `address` row: required).

## Out of scope
- Geocoding or address autocomplete.
- Deriving the pin from the address.
- Structured address fields.

## Manual verification
- Create a listing without an address → error. With one → it shows under the name in the panel and page, and in the result card.
- At 390 px, a long address truncates in the card and wraps on the page.
