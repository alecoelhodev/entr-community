# T11: Retry review writes on transient transaction errors

**Status:** in review
**Depends on:** — (MVP done)
**User stories:** US-11, US-12 (reliability)

## Goal
When MongoDB aborts a review transaction because of a write conflict, the request retries it instead of returning a 500. The rating aggregate is never applied twice.

## Context
- Since T08, each review write and its rating delta run inside `django_mongodb_backend.transaction.atomic()`. Django's own `transaction.atomic()` is a no-op on this backend. Callers:
  - `review_create`, `review_update`, `review_delete` in `apps/directory/views.py`.
  - `ReviewAdmin._set_hidden` in `apps/directory/admin.py`.
- On a concurrent conflict, MongoDB aborts with an error labelled `TransientTransactionError`. Retrying the whole transaction is then safe, because nothing was committed.
- The backend wraps pymongo errors as `DatabaseError(str(e)) from e` (`django_mongodb_backend/query.py`), so the label is on `__cause__`. Errors raised while committing may be raw `PyMongoError`s.
- `UnknownTransactionCommitResult` means the commit may have succeeded. Replaying the whole transaction would double-apply the rating delta, so it must **not** be retried this way.

## Acceptance criteria
- New `apps/directory/transactions.py` with `run_in_transaction(fn, attempts=3)`:
  - Runs `fn()` inside `atomic()` and returns its result.
  - On `DatabaseError` or `PyMongoError`, it retries only when the error, or its `__cause__`, has the `TransientTransactionError` label. Backoff is short, about 20/40/80 ms with jitter.
  - Any other error is re-raised immediately. After the last attempt, the last error is re-raised.
- All four callers use it.
  - Each attempt builds its unsaved objects afresh from validated data, so a retry never reuses a pk assigned inside an aborted transaction.
  - `review_create` keeps its explicit duplicate check and its `IntegrityError` → form error handling.
- No change in behavior when there's no conflict. The T08 tests still pass unchanged.

## Tests to write first
`apps/directory/tests/test_transactions.py` → `RunInTransactionTests`, `ReviewRetryTests`
- `test_retries_transient_then_succeeds`: `fn` raises a transient-labelled error once → called twice, and the result is returned.
- `test_transient_label_on_cause_detected`: `DatabaseError` whose `__cause__` is a labelled `PyMongoError`.
- `test_non_transient_raised_immediately`: `fn` is called once.
- `test_unknown_commit_result_not_retried`.
- `test_gives_up_after_attempts`: always transient → raises after 3 calls.
- `test_create_review_retry_applies_aggregate_once`: patch `apply_rating_delta` to fail transiently once on create. Expect 302, exactly one `Review`, and the aggregate `+rating/+1`.

Patch `time.sleep` (or the module's sleep) so the tests don't wait.

## Implementation notes
- Build the test errors with `pymongo.errors.OperationFailure` (or `PyMongoError`) and `_add_error_label("TransientTransactionError")`, or with a small subclass whose `has_error_label` returns `True`.
- Log each retry at WARNING on the server (attempt number and error code only; no request data).
- CLAUDE.md: one line in the reviews bullet saying review writes go through `run_in_transaction`.

## Out of scope
- Retrying non-review writes.
- A general-purpose retry decorator for every view.
- Handling `UnknownTransactionCommitResult` with commit-only retry.

## Manual verification
None beyond the tests. Write conflicts can't be triggered reliably by hand. Note in the PR that the T08 manual review flow still behaves the same.
