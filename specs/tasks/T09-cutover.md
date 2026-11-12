# T09: Cutover: remove `places`, Doral seed data

**Status:** in progress
**Depends on:** T05, T07, T08
**User stories:** US-1 (demo data)

## Goal
The starter's example `places` app is gone. A seed command loads realistic Doral sample data. Docs, CI and the smoke test point at the directory.

## Context
- To remove:
  - `apps/places/`, including `management/commands/seed_places.py`.
  - `templates/places/`.
  - Its URL include in `config/urls.py`.
  - Its entry in `INSTALLED_APPS`.
- The workflow smoke test currently checks `/places.geojson?bbox=-9.2,38.6,-9.0,38.8` (Lisbon).
- `LatLngFieldsMixin` (T02) stays in `apps/geo`. Remove `PlaceAdminForm`.

## Acceptance criteria
- `python manage.py seed_directory` creates sample data and is idempotent. Run twice, it creates no duplicates; key on the category slug and the business slug.
  - Categories: Bakery, Printing & Apparel, Music Lessons, Food Truck, Beauty, Home Services, plus whatever else the data needs.
  - At least 8 approved businesses inside the Doral bbox `-80.40,25.78,-80.30,25.86`, including:
    - A bakery offering "Golfeados" and "Cachitos" with prices.
    - A t-shirt printing shop.
    - A guitar teacher ("Guitar lessons", "per hour").
  - Varied `started_on` values. Some businesses have `offers_delivery`, and some have an Instagram handle. Use obviously fake handles like `example_bakery`.
  - Owned by a seed user `seed@example.invalid` with an unusable password.
- No `places` code, templates, URLs or tests remain. `git grep -i "places"` finds only historical docs, if any.
- The workflow smoke test checks `/` and `/businesses.geojson?bbox=-80.40,25.78,-80.30,25.86`.
- README, CLAUDE.md (commands, architecture, the single-test example) and `docs/deployment.md` refer to the directory.

## Tests to write first
`apps/directory/tests/test_seed.py` → `SeedDirectoryTests`
- `test_seed_creates_approved_businesses_in_doral`: all seeded businesses fall inside the bbox and are approved.
- `test_seed_idempotent`: two runs give the same counts.
- `test_seed_data_searchable`: after seeding, the `q=golfeados` GeoJSON returns the bakery, and `q=guitar` returns the teacher.
- `test_seed_user_cannot_log_in`.

## Implementation notes
- Update the CLAUDE.md single-test example to a directory test, e.g. `apps.directory.tests.test_api.BusinessGeoJSONTests.test_geojson_search_matches_offering`.
- **⚠ confirm.** Ask a human before running either production step:
  1. Drop the leftover `places_place` collection on Atlas.
  2. Optionally run `seed_directory` against production. That puts demo businesses on the live map; decide whether it's wanted.

  Both are manual and run by a human, not in CI.
- Don't commit any connection strings or hostnames.

## Out of scope
- New features.
- Spanish locale.
- Tile provider change (tracked in product.md known risks).

## Manual verification
- `docker compose down --volumes && docker compose up --build -d`, then `migrate`, then `seed_directory`. The map in Doral shows the seeded businesses; searching for "golfeados" works.
- After merging, the deploy's smoke test passes.
