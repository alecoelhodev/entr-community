# UI design (approved)

The approved mockups are at https://claude.ai/artifact/PVv2PjiiMunuoWRnFed2wV. The link is private to the owner; agents with access can read it with the Artifact tool's `read` action. Build every screen to match it. This file records what you need when the canvas isn't available.

| Screen (artboard) | Route | Task |
|---|---|---|
| Map: search results (`Main`) | `/` | T05 (+ T04 data) |
| Map: business panel (`Panel`) | `/` with `/b/<slug>/panel/` in the sidebar | T05, T06 |
| Business page + reviews (`Detail`) | `/b/<slug>/` | T06, T08 |
| Mobile: map + sheet (`Mobile`) | `/` at phone width | T05 |
| Sign up (`Signup`) | `/accounts/signup/` (login reuses the card) | T01 |
| Vendor: my businesses (`Dashboard`) | `/me/businesses/` | T07 |
| Vendor: new listing (`ListingForm`) | `/me/businesses/new/`, `…/edit/` | T07 |

## Tokens

Define these as CSS custom properties in `static/css/app.css`. Don't hard-code hex values in templates.

| Token | Value | Use |
|---|---|---|
| `--bg` | `#F6F5F1` | Page background |
| `--surface` | `#FFFFFF` | Cards, header, sidebar |
| `--ink` | `#16191D` | Text, primary dark buttons |
| `--ink-2` | `#3D434A` | Secondary text, labels |
| `--muted` | `#5B6168` | Hints, meta (passes 4.5:1 on white) |
| `--line` | `#E3E1DA` | Card borders, dividers |
| `--input-line` | `#D6D3CA` | Form control borders |
| `--accent` | `#0F6E66` | Links, primary buttons, map pins, category chip text |
| `--accent-soft` | `#EEF5F3` | Category chip background |
| `--selected` | `#C2700E` | Selected map pin |
| `--star` | `#E8A33D` | Star icon fill (decorative only) |
| `--neutral-chip` | `#F0EEE8` | "Delivery" badge background |
| Status: approved | `#E1F2EF` bg / `#0B5C55` text | Dashboard badge |
| Status: pending | `#FCF1DC` / `#7A4E00` | Dashboard badge |
| Status: rejected | `#FBE6E1` / `#9A3324` | Badge, error text, invalid input border |
| Map land / park / water / major road | `#E9EDE5` / `#D9E8CF` / `#CFE1EC` / `#F3E3BC` | Mockup only. Real tiles come from `MAP_TILE_URL` |

## Type

- Headings use **Space Grotesk** 600–700. Body text uses **Inter** 400/500/600, 15 px base, and 16 px in inputs to prevent zoom on iOS.
- **The CSP blocks Google Fonts.** Vendor the `woff2` files into `static/vendor/fonts/`, list them in `static/vendor/VERSIONS`, and declare `@font-face` in `app.css`. Keep `font-display: swap` and a `system-ui` fallback. Both fonts are under the SIL Open Font License; include the license files.

## Components

- **Header:** logo mark (an accent rounded square with a pin icon) and the "entr community" wordmark.
  - Logged out: "List your business", "Log in", "Sign up" (dark button).
  - Logged in: "My businesses", the user's first name, and "Log out" (a POST form button).
- **Category chip:** pill with `--accent-soft` background and `--accent` text, 13 px semibold.
- **Delivery badge:** pill with `--neutral-chip` background, `--ink` text and a truck icon. Shown only when `offers_delivery`. Reads "Offers delivery" on the panel and page, and "Delivery" in compact lists.
- **Rating:** star icon, the average in bold, then "(N reviews)". "No reviews yet" when the count is 0.
- **Offering row/card:** name in bold, description in muted text, and a price line: "From $X.XX <note>", or "Ask for price".
- **Contact list:** address, phone (`tel:`), website, Instagram (`@handle` linking to `https://www.instagram.com/<handle>/`). External links use `rel="noopener nofollow ugc" target="_blank"`. Each row renders only if set.
- **Status badge:** a dot plus a label: "Approved · live on the map", "Pending review", or "Needs changes" (the label for `rejected`). A rejected listing also shows a "Moderator note" box with the `rejection_reason`.
- **Buttons:**
  - Primary: `--accent` background, white text, 12 px radius, ≥ 48 px tall.
  - Secondary: white with a `--input-line` border.
  - All touch targets are ≥ 44 px.
- **Map pins:** 34 px `--accent` circle with a 3 px white border. The selected pin is 42 px, `--selected`, with a soft halo. Use Leaflet `divIcon` with a CSS class (no inline styles).

## Layout

- Map pages: sidebar 380–440 px plus a fluid map. Below about 900 px they stack (flex-wrap). The phone layout follows the `Mobile` artboard: a floating search bar, horizontally scrolling category chips, and a bottom sheet for the selected business.
- Content pages: centered, `max-width` 880–1120 px, cards with a 14–16 px radius and a 1 px `--line` border.
