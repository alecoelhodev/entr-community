# Product: community business map

## Vision

A map that connects local entrepreneurs with people nearby. Vendors such as bakers, printers and music teachers list their business, services and prices. People find them by category or by searching for a product ("golfeados", "cachitos", "t-shirt printing") and see the results on the map.

The approved UI design is in [design.md](design.md).

## Personas

- **Customer.** New in town, or just looking. Needs a product or service close by, for example t-shirt printing for a project.
- **Vendor.** A small business or independent professional, such as a guitar teacher or a home bakery. Wants to be discovered by people in the community.
- **Moderator.** A staff member who approves listings and hides abusive reviews.

## User stories

| ID | As a… | I want to… | So that… | Task |
|---|---|---|---|---|
| US-1 | customer | see businesses on a map around Doral, FL | I can find what's near me | T04, T05 |
| US-2 | customer | filter the map by category | I only see the kind of business I need | T04, T05 |
| US-3 | customer | search for a product or service ("golfeados") | I find vendors that offer it, even if it isn't in their name | T03, T04, T05 |
| US-4 | customer | click a business and see its details: category, services, prices, rating, reviews, time in business, whether it delivers, and its Instagram | I can decide whether to contact it | T06, T05 |
| US-5 | customer | list businesses nearest to a point, matching my filters | I can compare nearby options | T04 |
| US-6 | visitor | create an account and log in with my email | I can review or list businesses | T01 |
| US-7 | vendor | create a listing with location, category, description, services and prices, my Instagram, and whether I deliver | customers can find me | T07 |
| US-8 | vendor | see whether my listing is pending, approved or rejected, and why | I know when I'm live | T07 |
| US-9 | vendor | edit my listing | it stays accurate | T07 |
| US-10 | moderator | approve or reject listings | only legitimate businesses appear | T02 |
| US-11 | customer | rate (1–5) and review a business once, and edit or delete my review | others benefit from my experience | T08 |
| US-12 | moderator | hide abusive reviews | the community stays trustworthy | T08 |
| US-13 | team | run CI on every PR | broken work never reaches `main` | T00 |

## Domain model

All new models live in `apps.directory`, except the user, which lives in `apps.accounts`. Primary keys are `ObjectIdAutoField` (project default).

### `accounts.User` (T01)
- `AbstractUser`, with `email` unique and used as the login identifier (`USERNAME_FIELD = "email"`).
- The email is never shown publicly. Reviews display `first_name`, or "Anonymous" if it's blank.

### `directory.Category` (T02)
- `name`, unique, and `slug`, unique. Flat; no hierarchy.
- Managed by staff in the admin.
- Ordered by `name`.

### `directory.Business` (T02)

| Field | Type | Notes |
|---|---|---|
| `owner` | FK `User` | `on_delete=CASCADE` |
| `name` | Char 120 | |
| `slug` | Slug, unique | Generated from `name` on create; a suffix is added on collision |
| `category` | FK `Category` | `on_delete=PROTECT` |
| `description` | Text, blank | |
| `location` | `PointField(srid=4326)` | Gets an automatic 2dsphere index |
| `address` | Char 200, blank | Free text; no geocoding in the MVP |
| `phone`, `website` | Char / URL, blank | Shown publicly; the vendor chooses whether to fill them |
| `instagram` | Char 30, blank | Handle only, stored without `@`. Must match `^[A-Za-z0-9._]{1,30}$`. Rendered as a link to `https://www.instagram.com/<handle>/`, never from a user-supplied URL |
| `offers_delivery` | Boolean, default False | Shows the "Delivery" badge |
| `started_on` | Date, null | Drives "Active since YYYY (N years)" |
| `status` | Char choices | `pending` (default) / `approved` / `rejected` |
| `rejection_reason` | Text, blank | Shown to the owner only |
| `offerings` | `EmbeddedModelArrayField(Offering)` | See below |
| `search_terms` | `ArrayField(CharField)` | Derived on `save()`; never edited directly |
| `rating_sum`, `rating_count` | PositiveInteger, default 0 | Denormalized and updated atomically (T08) |
| `created_at`, `updated_at` | DateTime | `auto_now_add` / `auto_now` |

- Manager: `objects = MongoManager()`, which `nearest()` needs, with an `approved()` queryset method.
- Properties:
  - `rating_avg`: `None` when `rating_count == 0`.
  - `years_active`: whole years since `started_on`, or `None`.

**`Offering`** is an `EmbeddedModel`. Fields:
- `name` (Char 80)
- `description` (Char 300, blank)
- `price_from` (Decimal, null, ≥ 0)
- `price_note` (Char 80, blank, e.g. "per hour", "per dozen")

All prices are USD in the MVP.

### `directory.Review` (T08)
- `business` FK, `author` FK `User`.
- `rating` (1–5), `text` (blank allowed, ≤ 2000 chars), `is_hidden` (default False).
- Timestamps.
- Unique constraint on `(business, author)`.

## Rules

- **Visibility.** Public pages, the map and search show only `approved` businesses. An owner sees their own listings in any status. Staff see everything.
- **Moderation.** New listings start as `pending`. Editing a `rejected` listing puts it back to `pending`. Editing an `approved` listing keeps it live (see open questions).
- **Reviews.**
  - One per user per business.
  - Owners can't review their own business.
  - Only approved businesses accept reviews.
  - Hidden reviews don't count toward the rating.
- **Search.** The query is normalized the same way as the stored `search_terms` (see T03). A business matches when it contains **all** query terms. Combined with the category filter and the map viewport, or with the radius for the nearby list.
- **Default map center.** Doral, FL: lat 25.8195, lng -80.3553, zoom 13.

## Technical decisions

- **Search uses a normalized `search_terms` array, not Atlas Search.**
  - The local Compose MongoDB is community `mongod` without `mongot`.
  - `$search` and `$geoNear` must each be the first pipeline stage, so they can't be combined.
  - The array approach works identically locally and on Atlas, and is unit-testable. Atlas Search can later replace it behind the same `q` parameter.
- **The ORM's `ArrayField__contains` compiles to `$setIntersection`, which is not index-backed.** That's acceptable inside a bbox-limited query capped at 500 results. The nearby list uses `$geoNear.query` with `{"search_terms": {"$all": [...]}}`, which can use indexes.
- **Rating aggregates use atomic `F()` deltas**, never read-modify-write, because Cloud Run runs several workers and instances.

## Non-goals for the MVP

- Password reset by email: needs an email provider and secret.
- Address geocoding: needs an external service.
- User geolocation.
- Atlas Search.
- Photos and uploads.
- Messaging between users.
- Spanish locale: strings are i18n-wrapped, so it's a translation-only follow-up.

## Known risks before public launch

- **No rate limiting or CAPTCHA** on signup, login or reviews. Add before announcing publicly.
- **OSM public tile server.** Set `MAP_TILE_URL` to a commercial or self-hosted provider (see `docs/deployment.md`).

## Open questions

- Should edits to an already-approved listing go back to moderation? MVP assumption: no. Staff can un-approve.
- Should phone and website be visible to anonymous users, or only to logged-in users? MVP assumption: visible.
