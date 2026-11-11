# Specs: how agents work this repo

The product is described in [product.md](product.md). The approved UI is in [design.md](design.md), which links the mockups; UI tasks build to it. The work is split into tasks under [tasks/](tasks/). Each task is small enough for one agent and one PR, and is written test-first.

## Status board

Update your row when you start (`in progress`) and when your PR merges (`done`).

| Task | Title | Depends on | Status |
|---|---|---|---|
| [T00](tasks/T00-ci-pr-checks.md) | CI checks on pull requests | — | done |
| [T01](tasks/T01-accounts.md) | Accounts: custom user, signup, login | — | ready |
| [T02](tasks/T02-directory-models.md) | Directory models + moderation admin | T01, T03 | blocked |
| [T03](tasks/T03-search-terms.md) | Search term normalization | — | in progress |
| [T04](tasks/T04-map-api.md) | Public map API (GeoJSON + nearby, filters) | T02 | blocked |
| [T05](tasks/T05-map-ui.md) | Map UI: filters, search, detail panel | T04, T06 | blocked |
| [T06](tasks/T06-business-detail.md) | Business detail page + panel | T02 | blocked |
| [T07](tasks/T07-vendor-dashboard.md) | Vendor dashboard: create/edit listings | T01, T02 | blocked |
| [T08](tasks/T08-reviews.md) | Reviews and rating aggregate | T01, T06 | blocked |
| [T09](tasks/T09-cutover.md) | Cutover: remove `places`, Doral seed data | T05, T07, T08 | blocked |

```
T00 (independent)

T01 ──┬──────────────────────────────────────┐
      ▼                                      │
T03 → T02 ─┬─ T04 ─┐                         │
           │       ├─ T05 ─┐                 │
           ├─ T06 ─┤       │                 │
           │       └─ T08 ◄┼─────────────────┤
           └─ T07 ◄────────┼─────────────────┘
                           ▼
              T09 (after T05, T07, T08)
```

T00, T01 and T03 can start in parallel. After T02 merges, T04, T06 and T07 can run in parallel.

## Workflow

1. Pick a `ready` task whose dependencies are all `done`. Read the task, [product.md](product.md) and [CLAUDE.md](../CLAUDE.md).
2. Branch from `main`: `t0X-<short-slug>`.
3. **Red:** write the tests listed under *Tests to write first*. Run them and confirm they fail for the expected reason (not an import error in an unrelated module). Commit: `test: <task> failing tests`.
4. **Green:** implement until the full suite passes. Keep to the task's scope.
5. **Refactor**, keeping the suite green.
6. Open a PR against `main` and include the task ID in its title. Set the board status.

**Never push to `main`.** Every push to `main` deploys to production (see [docs/deployment.md](../docs/deployment.md)).

## Rules

- Run everything through Docker Compose. The image carries GDAL/GEOS; don't run Django on the host.
  ```sh
  docker compose up --build -d
  docker compose exec web python manage.py test
  docker compose exec web python manage.py makemigrations --check --dry-run
  ```
- The constraints in [CLAUDE.md](../CLAUDE.md) are binding. In particular:
  - Strict CSP: no inline `<script>` or `<style>`, and no CDNs.
  - Alpine CSP build: register components with `Alpine.data()` in a static JS file.
  - Coordinate order: GEOS/GeoJSON is `(lng, lat)`, Leaflet is `[lat, lng]`.
  - Respect the MongoDB backend's lookup limits.
- Validate request input at the boundary with Django forms. Invalid input returns 400 with form errors only, never stack traces or DB errors.
- Enforce authorization in views, server-side. Hiding a button is not enforcement.
- Read-only views use `@require_safe`. State-changing views are POST-only and CSRF-protected.
- New user-facing strings use `{% translate %}` / `gettext`, because a Spanish locale follows the MVP.
- No new dependency without a pinned version range and a one-line rationale in the PR.
- Don't fix unrelated things; mention them in the PR instead.

## Definition of done

- [ ] Every test under *Tests to write first* exists and failed before the change.
- [ ] `docker compose exec web python manage.py test` passes.
- [ ] `makemigrations --check --dry-run` reports no changes.
- [ ] *Manual verification* steps were done and noted in the PR.
- [ ] CLAUDE.md is updated if a command, convention or architecture fact changed.
- [ ] Any step marked **⚠ confirm** was approved by a human before it ran.

## Task file template

```markdown
# TXX: Title

**Status:** ready | blocked | in progress | done
**Depends on:** …
**User stories:** US-…

## Goal
## Context
## Acceptance criteria   (Given / When / Then)
## Tests to write first  (module → class → test method: what it asserts)
## Implementation notes
## Out of scope
## Manual verification
```
