# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack

Django 6.1 server-rendered templates + HTMX + Alpine.js (CSP build) + Leaflet/OSM, on MongoDB 8 via the official `django-mongodb-backend` (with GeoDjango). Everything runs in Docker Compose; the image carries GDAL/GEOS/PROJ, so don't run Django on the host.

## Commands

```sh
docker compose up --build -d                              # mongo (single-node replica set rs0) + web (runserver)
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_places      # Lisbon sample data, idempotent
docker compose exec web python manage.py createsuperuser  # prompts for email (no username)
docker compose exec web python manage.py test             # all tests (uses a real Mongo test DB)
docker compose exec web python manage.py test apps.geo.tests.test_queries.GeoQueryTests.test_nearest_limit   # single test
docker compose exec web python manage.py makemigrations <app>
docker compose exec web uv lock                           # after editing pyproject.toml; then rebuild
```

Deps are managed with `uv` inside the image (`UV_PROJECT_ENVIRONMENT=/opt/venv`); `uv.lock` is committed. No linter is configured.

## Architecture

Product specs and agent tasks (test-first): `specs/`. Start with `specs/README.md`. UI work follows the approved design in `specs/design.md`.

- `apps/accounts/` — custom `User` (`AUTH_USER_MODEL = "accounts.User"`): no `username`, email is the login field and is lowercased on save, so the unique index is case-insensitive. URLs: `/accounts/signup/`, `/accounts/login/`, `/accounts/logout/` (POST only).
- `config/` — settings (single env-driven file), urls. `config/apps.py` holds ObjectId-based AppConfigs for contrib apps.
- `apps/geo/` — reusable geo foundation, no models:
  - `forms.py` validates request coordinates at the boundary (`NearbyQueryForm`: lat/lng/radius ≤ 50 km; `BBoxForm`: `west,south,east,north`, span ≤ 5°).
  - `queries.py`: `near` / `in_bbox` (ORM lookups) and `nearest` (`$geoNear` via `raw_aggregate`, sets `distance_m` on each result).
  - `geojson.py`: objects → FeatureCollection.
- `apps/places/` — example domain app using the foundation. Views: map page, bbox → GeoJSON (capped at 500), nearby → HTMX partial (capped at 50). Invalid input returns 400 with form errors only.
- Front end: `static/js/map.js` registers `Alpine.data("placesMap")`; Leaflet fetches GeoJSON on debounced `moveend`, map click calls `htmx.ajax` to swap the nearby partial. URLs and tile URL are passed via `data-*` attributes from `templates/places/map.html`.

## MongoDB backend gotchas

- Primary keys are `ObjectIdAutoField`. Any contrib/third-party app with models needs an ObjectId AppConfig in `config/apps.py` and its migrations generated into `mongo_migrations/<app>/` (registered in `MIGRATION_MODULES`).
- Swapping `AUTH_USER_MODEL` or reordering migrations under an already-migrated DB raises `InconsistentMigrationHistory`. Locally, reset with `docker compose down --volumes`, then `migrate`. In production, a human drops the Atlas database before the merge deploys.
- Spatial fields: SRID 4326 only, stored as GeoJSON with an automatic `2dsphere` index. Supported lookups: `within`, `intersects`, `contains`, `disjoint`, `distance_lte/gt` (accepts `D(km=…)`), `dwithin` (degrees only). No GIS DB functions (`Distance()` etc.) — use `apps.geo.queries.nearest` for distance-sorted results; the model needs `objects = MongoManager()`.
- Coordinate order: GEOS/GeoJSON `(lng, lat)`; Leaflet `[lat, lng]`. Conversion happens only in `apps/geo/forms.py` and `static/js/map.js`.
- Django's admin OSM map widget loads OpenLayers from a CDN that the CSP blocks, so `PlaceAdmin` uses plain lat/lng form fields.

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

Env vars (see `.env.example`): `DJANGO_DEBUG`, `DJANGO_SECRET_KEY` (required when DEBUG is off — settings raise otherwise), `DJANGO_ALLOWED_HOSTS`, `MONGODB_URI`, `MONGODB_NAME`, `MAP_TILE_URL`. The public OSM tile server is for light use only; switch `MAP_TILE_URL` before production traffic.
