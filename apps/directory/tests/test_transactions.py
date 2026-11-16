from unittest import mock

from django.db import DatabaseError
from django.test import SimpleTestCase
from pymongo.errors import OperationFailure

from apps.directory.models import Review
from apps.directory.ratings import apply_rating_delta
from apps.directory.transactions import run_in_transaction

from .test_reviews import ReviewTestCase


def labelled(label):
    err = OperationFailure("simulated", code=112)
    err._add_error_label(label)
    return err


def transient():
    return labelled("TransientTransactionError")


def wrapped(cause):
    """How django-mongodb-backend surfaces pymongo errors: DatabaseError(...) from e."""
    try:
        raise DatabaseError(str(cause)) from cause
    except DatabaseError as e:
        return e


@mock.patch("apps.directory.transactions.atomic", mock.MagicMock())
@mock.patch("apps.directory.transactions.sleep")
class RunInTransactionTests(SimpleTestCase):
    def test_retries_transient_then_succeeds(self, sleep):
        fn = mock.Mock(side_effect=[transient(), "ok"])
        self.assertEqual(run_in_transaction(fn), "ok")
        self.assertEqual(fn.call_count, 2)
        sleep.assert_called_once()

    def test_transient_label_on_cause_detected(self, sleep):
        fn = mock.Mock(side_effect=[wrapped(transient()), "ok"])
        self.assertEqual(run_in_transaction(fn), "ok")
        self.assertEqual(fn.call_count, 2)

    def test_non_transient_raised_immediately(self, sleep):
        fn = mock.Mock(side_effect=DatabaseError("boom"))
        with self.assertRaises(DatabaseError):
            run_in_transaction(fn)
        self.assertEqual(fn.call_count, 1)
        sleep.assert_not_called()

    def test_unknown_commit_result_not_retried(self, sleep):
        err = labelled("UnknownTransactionCommitResult")
        err._add_error_label("TransientTransactionError")
        fn = mock.Mock(side_effect=wrapped(err))
        with self.assertRaises(DatabaseError):
            run_in_transaction(fn)
        self.assertEqual(fn.call_count, 1)

    def test_gives_up_after_attempts(self, sleep):
        fn = mock.Mock(side_effect=[transient(), transient(), transient()])
        with self.assertRaises(OperationFailure):
            run_in_transaction(fn)
        self.assertEqual(fn.call_count, 3)
        self.assertEqual(sleep.call_count, 2)


def flaky_delta(calls):
    """apply_rating_delta that fails transiently on its first call, then applies for real."""
    def delta(*args):
        calls.append(args)
        if len(calls) == 1:
            raise wrapped(transient())
        apply_rating_delta(*args)
    return delta


@mock.patch("apps.directory.transactions.sleep")
class ReviewRetryTests(ReviewTestCase):
    def test_create_review_retry_applies_aggregate_once(self, sleep):
        calls = []
        with mock.patch("apps.directory.views.apply_rating_delta", side_effect=flaky_delta(calls)):
            res = self.post_review(self.alice, 4)
        self.assertRedirects(res, self.url("detail"), fetch_redirect_response=False)
        self.assertEqual(len(calls), 2)
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(self.aggregate(), (4, 1))

    def test_update_review_retry_applies_delta_once(self, sleep):
        self.post_review(self.alice, 5)
        calls = []
        with mock.patch("apps.directory.views.apply_rating_delta", side_effect=flaky_delta(calls)):
            res = self.client.post(self.url("review_update"), {"rating": "2", "text": "Meh"})
        self.assertRedirects(res, self.url("detail"), fetch_redirect_response=False)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.aggregate(), (2, 1))
