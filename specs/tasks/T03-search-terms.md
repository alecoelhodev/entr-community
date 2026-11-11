# T03: Search term normalization

**Status:** ready
**Depends on:** —
**User stories:** US-3

## Goal
Pure functions that turn free text (business data or a user's query) into a normalized list of search terms. The query "Golfeados" must match a business offering "golfeado".

## Context
- This is the first file of the new `apps/directory` app. Create the app package (`apps/directory/__init__.py`, `apps.py`) and add it to `INSTALLED_APPS`. Models come in T02.
- See the search decisions in [product.md](../product.md#technical-decisions).

## Acceptance criteria
- `normalize_terms(text: str) -> list[str]`:
  - Lowercases.
  - Folds accents (`"Café"` → `cafe`, `"piñata"` → `pinata`).
  - Splits on anything that isn't a letter or digit.
  - Drops stopwords and tokens shorter than 2 characters.
  - Naively singularizes. Tokens longer than 3 characters ending in a single `s` (not `ss`) lose that `s`. For example `"printers"` → `printer`, `"clases"` → `clase`, `"business"` is unchanged. Exact linguistic accuracy is not a goal; because both stored terms and queries go through the same rule, matching stays consistent.
  - Deduplicates while preserving first-seen order.
- `query_terms(q: str) -> list[str]` runs the same pipeline, capped at **8 terms**.
- Bounds:
  - Input longer than 10 000 characters is truncated before processing.
  - Each term is capped at 40 characters.
  - `normalize_terms` returns at most 200 terms.

## Tests to write first
`apps/directory/tests/test_search.py` → `NormalizeTermsTests`
- `test_plural_spanish`: `"Golfeados"` → `["golfeado"]`; `"cachitos"` → `["cachito"]`.
- `test_plural_english`: `"T-Shirt Printing"` → `["shirt", "printing"]` (`"t"` dropped for length); `"printers"` → `["printer"]`; `"business"` → `["business"]`.
- `test_accent_folding`: `"Café Piñata"` → `["cafe", "pinata"]`.
- `test_stopwords_dropped`: `"clases de guitarra para niños"` → `["clase", "guitarra", "nino"]`; `"the best bakery"` → `["best", "bakery"]`.
- `test_empty_and_whitespace`: `""`, `"   "` and `"--"` → `[]`.
- `test_idempotent`: `normalize_terms(" ".join(normalize_terms(x))) == normalize_terms(x)` for a few samples.
- `test_dedup_preserves_order`.
- `test_bounds`: a 50 000-char input doesn't hang and returns ≤ 200 terms, each ≤ 40 chars.

`QueryTermsTests`
- `test_same_pipeline_as_normalize`.
- `test_caps_term_count`: a 20-word query → 8 terms.

## Implementation notes
- Stdlib only: `unicodedata.normalize("NFKD", …)`, then drop combining marks, then `re.findall(r"[a-z0-9]+", …)`.
- Keep the stopword sets small and explicit (English and Spanish, about 30 words each) as module-level `frozenset`s.
- Regex runs on bounded input only, so there's no ReDoS risk. Still, don't build regexes from user input.

## Out of scope
Stemming libraries; synonyms ("t-shirt" ≈ "camiseta"); fuzzy matching. Atlas Search handles those later.

## Manual verification
None beyond tests.
