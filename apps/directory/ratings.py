"""The only code that changes Business.rating_sum / rating_count.

Cloud Run runs several workers and instances, so every change is an atomic
`$inc`-style F() update, never a read-modify-write. Callers pair the review
write and the delta inside `django_mongodb_backend.transaction.atomic()`
(Django's own `transaction.atomic()` is a no-op on this backend).
"""

from django.db.models import F
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Business, Review


def apply_rating_delta(business_id, sum_delta: int, count_delta: int) -> None:
    Business.objects.filter(pk=business_id).update(
        rating_sum=F("rating_sum") + sum_delta, rating_count=F("rating_count") + count_delta
    )


@receiver(post_delete, sender=Review, dispatch_uid="review_deleted_rating")
def _review_deleted(sender, instance, **kwargs):
    # Covers every delete path: the view, the admin and cascades (e.g. a deleted user).
    if not instance.is_hidden:
        apply_rating_delta(instance.business_id, -instance.rating, -1)
