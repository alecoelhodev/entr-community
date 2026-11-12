# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack

Django 6.1 server-rendered templates + HTMX + Alpine.js (CSP build) + Leaflet/OSM, on MongoDB 8 via the official `django-mongodb-backend` (with GeoDjango). Everything runs in Docker Compose; the image carries GDAL/GEOS/PROJ, so don't run Django on the host.

## Commands

```sh
docker compose up --build -d                              # mongo (single-node replica set rs0) + web (runserver)
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_directory   # fictional Doral demo businesses, idempotent
docker compose exec web python manage.py createsuperuser  # prompts for email (no username)
docker compose exec web python manage.py test             # all tests (uses a real Mongo test DB)
docker compose exec web python manage.py test apps.directory.tests.test_api.BusinessGeoJSONTests.test_geojson_search_matches_offering   # single test
docker compose exec web python manage.py makemigrations <app>
docker compose exec web uv lock                           # after editing pyproject.toml; then rebuild
```

Deps are managed with `uv` inside the image (`UV_PROJECT_ENVIRONMENT=/opt/venv`); `uv.lock` is committed. No linter is configured.

## Architecture

Product specs and agent tasks (test-first): `specs/`. Start with `specs/README.md`. UI work follows the approved design in `specs/design.md`.

- `apps/accounts/` — custom `User` (`AUTH_USER_MODEL = "accounts.User"`): no `username`, email is the login field and is lowercased on save, so the unique index is case-insensitive. URLs: `/accounts/signup/`, `/accounts/login/`, `/accounts/logout/` (POST only).
- `config/` — settings (single env-driven file), urls. `config/apps.py` holds ObjectId-based AppConfigs for contrib apps.
- `apps/geo/` — reusable geo foundation, no models:
  - `forms.py` validates request coordinates at the boundary (`NearbyQueryForm`: lat/lng/radius ≤ 50 km; `BBoxForm`: `west,south,east,north`, span ≤ 5°). `LatLngFieldsMixin` gives ModelForms plain lat/lng inputs for a PointField (`set_initial_from()` / `point`).
  - `queries.py`: `near` / `in_bbox` (ORM lookups) and `nearest` (`$geoNear` via `raw_aggregate`, sets `distance_m` on each result; optional `query` is a raw Mongo filter inside `$geoNear`, built only from validated values and stored column names such as `category_id`).
  - `geojson.py`: objects → FeatureCollection.
- `apps/directory/` — the product domain:
  - `search.py`: `normalize_terms` / `query_terms`.
  - `models.py`: `Category`; `Business` with embedded `Offering`s (`EmbeddedModelArrayField`). `Business.save()` generates the slug on create and refreshes `search_terms`; `Business.objects.approved()` is the public visibility filter.
  - `admin.py`: approve and reject actions.
  - Public API: `/businesses.geojson?bbox=&category=&q=` (approved only, capped at 500) and `/businesses/nearby/?lat&lng&radius_km&category&q` (HTMX partial, capped at 50). Both validate filters with `BusinessFilterForm`; `q` must match **all** normalized terms. `raw_aggregate` results can't `select_related`, so resolve FKs with one `in_bulk` query.
  - Detail: `/b/<slug>/` (page) and `/b/<slug>/panel/` (HTMX partial) share `templates/directory/_detail_body.html`. `get_visible_business()` is the single visibility rule: approved for everyone, any status for the owner and staff, else 404. Render vendor URLs through `Business.website_url` (http/https only), never `website` directly.
  - Vendor pages (login required): `/me/businesses/`, `/me/businesses/new/`, `/me/businesses/<slug>/edit/`. `BusinessForm` + `OfferingFormSet` (≤ 10 rows, blank names ignored, ≥ 1 required). Edits are scoped with `owner=request.user` (others get 404); the view, not the form, moves `rejected` → `pending`. Location picker: `static/js/location-picker.js` (`Alpine.data("locationPicker")`), loaded only on the form page.
- Reviews: `Review` (one per author per business). POST-only `/b/<slug>/reviews/`, `…/reviews/mine/`, `…/reviews/mine/delete/`. **Only `apps/directory/ratings.py` changes `rating_sum`/`rating_count`**, via atomic `F()` deltas. The view, the admin hide/unhide actions and a `post_delete` signal (which covers cascades) call it. `Business.save()` never writes the rating fields on update, so a stale instance can't clobber them.
- `templates/_field.html` renders one form field (label, widget, help, errors) for the account and listing forms.
- Front end: `/` is `templates/directory/map.html` with `static/js/map.js` (`Alpine.data("directoryMap")`).
  - URLs, tile URL, center and zoom come from `data-*` attributes. The panel URL is a template (`/b/__slug__/panel/`); JS substitutes `encodeURIComponent(slug)`.
  - Category and search (`x-model`, 300 ms debounce on `q`) reload the markers on debounced `moveend` (`AbortController` cancels stale fetches) and the nearby list via `htmx.ajax` into `#nearby`. Nearby starts at the default center; a map click moves it.
  - Marker or result-card clicks load the panel into `#detail`. The panel's close buttons call `closePanel` (Alpine binds them after the swap, inside the component's scope).
  - Tooltips are built with DOM text nodes, never HTML strings: Leaflet sets string tooltips as `innerHTML`.
  - Below 900 px the sidebar uses `display: contents`, so filters, map and results stack, and the panel becomes a fixed bottom sheet.

## MongoDB backend gotchas

- Primary keys are `ObjectIdAutoField`. Any contrib/third-party app with models needs an ObjectId AppConfig in `config/apps.py` and its migrations generated into `mongo_migrations/<app>/` (registered in `MIGRATION_MODULES`).
- Swapping `AUTH_USER_MODEL` or reordering migrations under an already-migrated DB raises `InconsistentMigrationHistory`. Locally, reset with `docker compose down --volumes`, then `migrate`. In production, a human drops the Atlas database before the merge deploys.
- `django.db.transaction.atomic()` is a no-op on this backend. For real multi-document transactions (replica set only; local `rs0` and Atlas both qualify), use `django_mongodb_backend.transaction.atomic()`.
- Spatial fields: SRID 4326 only, stored as GeoJSON with an automatic `2dsphere` index. Supported lookups: `within`, `intersects`, `contains`, `disjoint`, `distance_lte/gt` (accepts `D(km=…)`), `dwithin` (degrees only). No GIS DB functions (`Distance()` etc.) — use `apps.geo.queries.nearest` for distance-sorted results; the model needs `objects = MongoManager()`.
- Coordinate order: GEOS/GeoJSON `(lng, lat)`; Leaflet `[lat, lng]`. Conversion happens only in `apps/geo/forms.py` and `static/js/map.js`.
- Django's admin OSM map widget loads OpenLayers from a CDN that the CSP blocks, so admin forms use `apps.geo.forms.LatLngFieldsMixin` instead.

## Front-end / CSP constraints

- Strict CSP via Django's built-in `ContentSecurityPolicyMiddleware` (`SECURE_CSP` in settings): scripts/styles `'self'` only, `img-src` adds the tile origin derived from `MAP_TILE_URL`. No CDNs, no inline scripts/styles.
- JS libs are vendored in `static/vendor/` (versions in `static/vendor/VERSIONS`); update the file when bumping. Production uses `CompressedManifestStaticFilesStorage`, so vendored files must have their referenced sourcemaps present or `collectstatic` fails.
- Alpine is the CSP build: define components with `Alpine.data()` in JS; templates may only use simple property access, no inline expressions. Alpine loads last in `base.html` so page scripts can register on `alpine:init`.
- Keep Leaflet objects in closure variables, not on the Alpine component (Alpine's reactive proxies break Leaflet).
- htmx is configured via a meta tag with `allowEval: false` and `includeIndicatorStyles: false`; CSRF token is sent through `hx-headers` on `<body>`.
- Views use `@require_safe` for read-only endpoints (GET + HEAD).

## Deployment

`.github/workflows/deploy-cloudrun.yml`: on pull requests to `main`, run the migrations check and tests only; on push to `main`, also build, push to Artifact Registry, `migrate` against Atlas from the new image, deploy to Cloud Run and smoke-test. Project-specific values come from GitHub repo variables, and secrets from Secret Manager. A new required env var must be added to the workflow's `env_vars`/`secrets`. Setup, gotchas and rollback are in `docs/deployment.md`.

## Config

Env vars (see `.env.example`): `DJANGO_DEBUG`, `DJANGO_SECRET_KEY` (required when DEBUG is off — settings raise otherwise), `DJANGO_ALLOWED_HOSTS`, `MONGODB_URI`, `MONGODB_NAME`, `MAP_TILE_URL`. Map default center/zoom are settings constants (`MAP_DEFAULT_CENTER`, Doral FL; `MAP_DEFAULT_ZOOM`), not env vars. The public OSM tile server is for light use only; switch `MAP_TILE_URL` before production traffic.
