# T00: CI checks on pull requests

**Status:** ready
**Depends on:** —
**User stories:** US-13

## Goal
Every PR runs the test suite and a migrations check. Only pushes to `main` (and manual runs) deploy.

## Context
- `.github/workflows/deploy-cloudrun.yml` currently triggers on `push` to `main` and `workflow_dispatch`. Its `test` job runs on `ubuntu-22.04` because of the MongoDB kernel check (see the comment in the workflow).
- The `deploy` job needs `id-token: write` and talks to GCP. It must never run for PRs, which includes PRs from forks.

## Acceptance criteria
- **Given** a PR against `main`, **when** it is opened or updated, **then** the `test` job runs and `deploy` is skipped.
- **Given** a push to `main` or a manual dispatch, **then** `test` runs and, if it passes, `deploy` runs, exactly as today.
- **Given** a model change without a migration, **then** the `test` job fails at the migrations check.

## Tests to write first
None; this is a workflow change. Verify it with real runs (see *Manual verification*).

## Implementation notes
- Add `pull_request: { branches: [main] }` to `on:`.
- On `deploy`, add `if: github.event_name == 'push' || github.event_name == 'workflow_dispatch'`.
- In the `test` job, run `python manage.py makemigrations --check --dry-run` in the same container invocation as the tests. One option is `docker compose run --rm web sh -c "python manage.py makemigrations --check --dry-run && python manage.py test"`.
- Keep `concurrency` as-is for deploys. Consider a separate concurrency group for PR runs keyed on `github.ref` with `cancel-in-progress: true`. That needs job-level concurrency, because the workflow-level group would serialize PRs behind deploys.
- Update the Deployment section of `docs/deployment.md` and the CLAUDE.md line about the workflow.

## Out of scope
Lint and format tooling; branch protection settings (a repo admin does this by hand, so suggest it in the PR description).

## Manual verification
- Open the T00 PR itself. In the Checks tab, `test` runs green and `deploy` shows as skipped.
- After merge, the push to `main` runs both jobs.
