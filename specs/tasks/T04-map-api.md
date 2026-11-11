# T04: Public map API: GeoJSON + nearby, with filters

**Status:** in progress
**Depends on:** T02
**User stories:** US-1, US-2, US-3, US-5

## Goal
Read-only endpoints feed the map: approved businesses in a viewport, and nearest businesses to a point, both filterable by category and search query.

## Context
- The existing pattern to mirror is `apps/places/views.py`:
  - `places_geojson` uses `BBoxForm` + `in_bbox` + `feature_collection`, capped at 500.
  - `places_nearby` uses `NearbyQueryForm` + `nearest`, capped at 50, and returns an HTMX partial.
- Reuse `apps/geo/forms.py`, `apps/geo/queries.py` and `apps/geo/geojson.py`. Don't duplicate them.
- `query_terms` comes from T03; `Business.objects.approved()` from T02.

## Acceptance criteria
- `GET /businesses.geojson?bbox=W,S,E,N[&category=<slug>][&q=<text>]` (name `directory:geojson`):
  - Returns approved businesses inside the bbox, at most 500.
  - Each feature's `properties` are `id`, `slug`, `name`, `category` (name), `rating_avg` and `offers_delivery`. Nothing else: no owner, no status.
  - `category` filters by slug. `q` requires **all** `query_terms(q)` to be in `search_terms`. A `q` that normalizes to `[]` applies no text filter.
- `GET /businesses/nearby/?lat&lng[&radius_km][&category][&q]` (name `directory:nearby`):
  - Returns an HTMX partial listing up to 50 approved businesses, nearest first.
  - Each row shows the name, category, distance, rating, and a "Delivery" badge when `offers_delivery` is set, and links to `/b/<slug>/`. The layout follows the result cards in [design.md](../design.md). T06 provides the route. Until then, render the slug without a link, or depend on T06 when merging.
- Validation, via a new `BusinessFilterForm` used by both views:
  - `category` must be an existing slug.
  - `q` ≤ 100 chars.
  - Errors → 400. GeoJSON returns `{"errors": …}`; the partial returns an error message. Same as the existing views.
- Both views use `@require_safe`.

## Tests to write first
`apps/geo/tests/test_queries.py` → `GeoQueryTests` (extend)
- `test_nearest_with_query_filters`: `nearest(..., query={"name": "X"})` returns only matching docs, still sorted by distance.
- `test_nearest_without_query_unchanged`: existing behavior is preserved.

`apps/directory/tests/test_forms.py` → `BusinessFilterFormTests`
- `test_unknown_category_invalid`, `test_q_too_long_invalid`, `test_blank_filters_valid`.

`apps/directory/tests/test_api.py` → `BusinessGeoJSONTests`, `BusinessNearbyTests`
- Fixtures in `setUpTestData`:
  - Doral businesses: a bakery offering "Golfeados" and "Cachitos", a print shop offering "T-shirt printing", a guitar teacher.
  - One pending bakery.
  - One approved business far away (e.g. Orlando).
- `test_geojson_returns_only_approved_in_bbox`: uses bbox `-80.40,25.78,-80.30,25.86`.
- `test_geojson_feature_properties_whitelist`: exact key set.
- `test_geojson_coordinates_lng_lat`.
- `test_geojson_filters_by_category`.
- `test_geojson_search_matches_offering`: `q=golfeados` → the bakery only.
- `test_geojson_search_all_terms_required`: `q=golfeados printing` → none.
- `test_geojson_bad_category_400`, `test_geojson_bad_bbox_400`.
- `test_geojson_cap_500`: patch the cap to 2 rather than inserting 501 docs.
- `test_nearby_sorted_by_distance_and_filtered`.
- `test_nearby_excludes_pending`.
- `test_nearby_is_partial`: no `<html`, with the `HX-Request` header.
- `test_nearby_invalid_400`.

## Implementation notes
- Extend `nearest(model, point, radius_km, limit, field="location", query=None)`: when `query` is given, set `$geoNear.query = query`. Update the docstring. The query is a raw MongoDB filter, so build it only from validated values, never from raw request strings:
  - `{"status": "approved"}`
  - `"category_id": <ObjectId>` from the validated `Category`. Check the actual stored column name in Mongo; FK columns are `<name>_id`.
  - `"search_terms": {"$all": terms}`
- GeoJSON path: `in_bbox(Business.objects.approved().select_related("category"), bbox)`, then `.filter(category=…)` and `.filter(search_terms__contains=terms)`.
  - `ArrayField__contains` isn't index-backed; that's acceptable here (see product.md).
  - Check that `select_related` avoids an N+1 on `category.name`. If the backend doesn't support it for this case, fetch the categories in one query and map them.
- `raw_aggregate` results don't run `select_related`. Resolve category names for the nearby list in **one** extra query (`Category.objects.in_bulk(ids)`), not per row.
- Keep `apps/places` URLs working; T09 removes them.

## Out of scope
- Front-end changes (T05).
- The detail page (T06).
- Pagination beyond the caps.

## Manual verification
With seeded or admin-created data, run
`curl 'localhost:8000/businesses.geojson?bbox=-80.40,25.78,-80.30,25.86&q=golfeados'`
and check the output.
