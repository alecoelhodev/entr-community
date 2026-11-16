# T10: MapTiler tiles

**Status:** done
**Depends on:** — (MVP done)
**User stories:** US-1 (launch readiness)

## Goal
Production map tiles come from MapTiler instead of the public OpenStreetMap servers, which forbid heavy use. The attribution MapTiler requires is shown. Switching provider stays a configuration change.

## Context
- `MAP_TILE_URL` (`config/settings.py`) already drives the tile layer and the CSP `img-src` origin. The origin is currently derived by string slicing (`_tile_origin`).
- The attribution is hard-coded to OpenStreetMap in `static/js/map.js` and `static/js/location-picker.js`.
- `MAP_TILE_URL` comes from the `MAP_TILE_URL` GitHub repo variable in `.github/workflows/deploy-cloudrun.yml`, falling back to OSM.
- The page-wide `Referrer-Policy` is `same-origin`. The tile layers set `referrerPolicy: "strict-origin-when-cross-origin"` so tile requests carry the origin, which MapTiler's domain-restricted keys need.
- The MapTiler key is a publishable browser key: it's visible in page source by design and restricted by allowed origins. It lives in a repo variable, not Secret Manager. It never goes in files or chat.

## Acceptance criteria
- New pure helper `config/tiles.py` with `tile_config(url) -> (origin, attribution_html)`:
  - `https://api.maptiler.com/...` → origin `https://api.maptiler.com`, attribution "© MapTiler © OpenStreetMap contributors", linking to MapTiler's and OSM's copyright pages.
  - Any other URL → its origin plus the current OSM attribution.
  - The `{s}.` subdomain placeholder still becomes a `*.` wildcard origin (existing behavior).
- `config/settings.py` uses `tile_config` for the CSP `img-src` origin and a new `MAP_TILE_ATTRIBUTION` setting. Attribution is derived from the host rather than read from a new env var, because HTML values don't survive the deploy action's comma/newline env parsing.
- The map page and the listing form render `data-tile-attribution`. Both JS files use it instead of the hard-coded string. They keep `referrerPolicy: "strict-origin-when-cross-origin"`.
- With the repo variable set, the deployed map loads MapTiler tiles with no CSP violations.

## Tests to write first
`config/tests/test_tiles.py` → `TileConfigTests`
- `test_maptiler_origin_and_attribution`.
- `test_osm_default_attribution`.
- `test_subdomain_placeholder_becomes_wildcard`.
- `test_attribution_has_no_key`: the attribution never contains the URL's query string.

`apps/directory/tests/test_map_page.py` (extend)
- `test_tile_attribution_attribute_present` on `/`.

`apps/directory/tests/test_vendor_views.py` (extend)
- The listing form renders `data-tile-attribution`.

## Implementation notes
- Check MapTiler's current docs for the raster XYZ URL format (expected: `https://api.maptiler.com/maps/streets-v2/256/{z}/{x}/{y}.png?key=…`) and the exact attribution wording. Use 256 px tiles so Leaflet needs no `tileSize` or `zoomOffset` changes.
- `config/` has no tests package yet. Add `config/tests/__init__.py`, or place the tests under `apps/geo/tests/` if discovery is simpler. Note the choice in the PR.
- Docs:
  - `docs/deployment.md` "Map tiles" section: create the key, restrict its origins, set the variable.
  - `.env.example`: a comment about a local MapTiler URL.
  - CLAUDE.md config line.
- **⚠ confirm: human steps.** You run these; the key never appears in chat, commits or logs.
  1. Create a MapTiler account and key. Allowed origins are bare hostnames with no protocol or port: the Cloud Run host (`entr-community-<project-number>.<region>.run.app`), plus `localhost` if you want MapTiler locally. Never `*.run.app`.
  2. Set the repo variable: `gh variable set MAP_TILE_URL --body 'https://api.maptiler.com/maps/streets-v2/256/{z}/{x}/{y}.png?key=<KEY>'`.

## Out of scope
- Vector tiles or MapLibre.
- Map style customization.
- Self-hosted tiles.

## Manual verification
- **Local, with `MAP_TILE_URL` set to a MapTiler URL:**
  - Tiles load and the attribution reads MapTiler + OSM.
  - The `Content-Security-Policy` header includes `https://api.maptiler.com`.
  - The headless-Chrome checklist from T05 reports no CSP violations.
- **After merge:** the live map uses MapTiler tiles. Check in the browser's network tab.
