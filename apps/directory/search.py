"""Search term normalization shared by stored business data and user queries.

Both sides go through the same pipeline, so a query for "Golfeados" matches a
business offering "golfeado" via an exact match on normalized terms.
"""

import re
import unicodedata

MAX_INPUT_CHARS = 10_000
MAX_TERM_CHARS = 40
MAX_TERMS = 200
MAX_QUERY_TERMS = 8

STOPWORDS_EN = frozenset(
    "a an and are as at be but by for from has have in is it its "
    "of on or our so than that the this to was we were with you your".split()
)
# Accent-folded, since matching happens after folding.
STOPWORDS_ES = frozenset(
    "al como con de del el en es esta este la las lo los mas mi mis "
    "muy o para pero por que se sin su sus un una unas uno unos y".split()
)
STOPWORDS = STOPWORDS_EN | STOPWORDS_ES

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _singularize(token: str) -> str:
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def normalize_terms(text: str) -> list[str]:
    """Return normalized, deduplicated search terms for ``text``, in order."""
    terms: dict[str, None] = {}
    for token in _TOKEN_RE.findall(_fold(text[:MAX_INPUT_CHARS])):
        if token in STOPWORDS:
            continue
        # Truncate before singularizing so a second pass is a no-op.
        term = _singularize(token[:MAX_TERM_CHARS])
        if len(term) < 2 or term in STOPWORDS:
            continue
        terms[term] = None
        if len(terms) == MAX_TERMS:
            break
    return list(terms)


def query_terms(q: str) -> list[str]:
    """Normalize a user query the same way as stored data, capped for querying."""
    return normalize_terms(q)[:MAX_QUERY_TERMS]
