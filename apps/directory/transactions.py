import logging
import random
from time import sleep

from django.db import DatabaseError
from django_mongodb_backend.transaction import atomic
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)


def _labels(exc):
    # The backend wraps pymongo errors as DatabaseError(...) from e, so check the cause too.
    for err in (exc, exc.__cause__):
        if isinstance(err, PyMongoError):
            return {label for label in ("TransientTransactionError", "UnknownTransactionCommitResult")
                    if err.has_error_label(label)}
    return set()


def _is_transient(exc):
    # UnknownTransactionCommitResult: the commit may have landed, so replaying could apply a delta twice.
    return _labels(exc) == {"TransientTransactionError"}


def run_in_transaction(fn, attempts=3):
    """Run fn() in a MongoDB transaction, retrying the whole transaction on TransientTransactionError.

    fn must build its unsaved objects afresh on each call: a retry must not reuse state from an aborted attempt.
    """
    for attempt in range(1, attempts + 1):
        try:
            with atomic():
                return fn()
        except (DatabaseError, PyMongoError) as exc:
            if attempt == attempts or not _is_transient(exc):
                raise
            code = getattr(exc.__cause__, "code", None) or getattr(exc, "code", None)
            logger.warning("Transient transaction error (code %s), retry %d of %d", code, attempt, attempts - 1)
            sleep(0.02 * 2 ** (attempt - 1) * random.uniform(1, 1.5))
