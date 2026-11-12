# T08: Reviews and rating aggregate

**Status:** ready
**Depends on:** T01, T06
**User stories:** US-11, US-12

## Goal
Logged-in customers can rate and review an approved business once, and edit or delete their review. Moderators can hide reviews. The business's rating stays correct under concurrent writes.

## Context
- `Business.rating_sum`, `rating_count` and `rating_avg` come from T02. The detail page and panel come from T06.
- Cloud Run runs several gunicorn workers and instances, so a read-modify-write on the aggregate would lose updates.

## Acceptance criteria
- `Review` model as defined in product.md, with a unique constraint on `(business, author)`.
- On `/b/<slug>/`, a logged-in non-owner sees a review form: rating 1–5 (radio) and text (≤ 2000 characters). If they already reviewed, they see their review with edit and delete.
- Routes, all POST-only and login required:
  - `POST /b/<slug>/reviews/` creates a review.
  - `POST /b/<slug>/reviews/mine/` updates it.
  - `POST /b/<slug>/reviews/mine/delete/` deletes it.
  - Each redirects back to the detail page, with HTMX support optional.
- Rules:

  | Request | Result |
  |---|---|
  | Anonymous | Redirect to login |
  | The business owner | 403 |
  | Business not approved | 404 |
  | Second review | Form error "You already reviewed this business" (200/400, not 500) |
  | Rating outside 1–5 | 400 |

- Aggregate:
  - Create adds `+rating` and `+1`.
  - Edit adds `new - old`.
  - Delete subtracts the rating and 1.
  - Hiding (admin action) subtracts, and unhiding adds back.
  - Hidden reviews aren't listed or counted.
  - Always use atomic `F()` updates.
- Listing: newest first, at most 20 on the detail page. Each shows the author's first name or "Anonymous", the rating, the date and the escaped text.
- Admin: `Review` list with filters (`is_hidden`, rating) and **Hide** / **Unhide** actions. The actions skip reviews already in the target state, so they're idempotent.

## Tests to write first
`apps/directory/tests/test_reviews.py` → `ReviewAggregateTests`, `ReviewViewTests`, `ReviewAdminTests`
- `test_create_increments_sum_and_count`.
- `test_edit_applies_delta`: 5 → 3 gives a sum of −2 with the count unchanged.
- `test_delete_decrements`.
- `test_hide_and_unhide_adjust_aggregate`.
- `test_hide_action_idempotent`: hiding twice decrements once.
- `test_aggregate_uses_atomic_update`:
  - Set up a business with `rating_sum=10, rating_count=2` in the DB.
  - Hold a stale in-memory instance with zeros.
  - Create a review.
  - The DB values become `+rating` and `+1` relative to 10/2, not to the stale values. This proves there's no read-modify-write.
- `test_anonymous_redirected_to_login`.
- `test_owner_cannot_review_403`.
- `test_pending_business_404`.
- `test_second_review_rejected_gracefully`.
- `test_rating_out_of_range_400`.
- `test_hidden_reviews_not_listed`.
- `test_review_text_escaped`.
- `test_author_email_never_rendered`.
- `test_get_not_allowed_on_mutations`: GET → 405.

## Implementation notes
- Put the aggregate logic in one place, e.g. `apps/directory/ratings.py`:
  ```python
  apply_rating_delta(business_id, sum_delta, count_delta)
  # -> Business.objects.filter(pk=…).update(rating_sum=F("rating_sum") + sum_delta, …)
  ```
  Call it from the views and admin actions.
  - Verify the backend translates `F()` arithmetic in `update()` into a single atomic update. The atomic-update test above enforces this.
- Pair each review write with its aggregate update. If the backend supports transactions on the replica set, wrap both in `transaction.atomic()` (the backend supports them on replica sets; check the pinned version). Otherwise document the residual risk in the PR.
- Catch `IntegrityError` from the unique constraint and turn it into a form error. Don't 500.

## Out of scope
- Vendor replies to reviews.
- Review voting and reporting.
- Rate limiting (known risk).

## Manual verification
Review a business as two different users, edit one review, hide the other in the admin, and check the detail page's average and count after each step.
