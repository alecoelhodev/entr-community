from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST, require_safe
from django_mongodb_backend.transaction import atomic

from apps.geo.forms import BBoxForm, NearbyQueryForm
from apps.geo.geojson import feature_collection
from apps.geo.queries import in_bbox, nearest

from .forms import BusinessFilterForm, BusinessForm, OfferingFormSet, ReviewForm
from .models import Business, Category, Review
from .ratings import apply_rating_delta

MAX_MAP_FEATURES = 500
MAX_NEARBY_RESULTS = 50


@require_safe
def map_page(request):
    lat, lng = settings.MAP_DEFAULT_CENTER
    return render(
        request,
        "directory/map.html",
        {
            "tile_url": settings.MAP_TILE_URL,
            "center_lat": lat,
            "center_lng": lng,
            "zoom": settings.MAP_DEFAULT_ZOOM,
            "categories": Category.objects.all(),
        },
    )


def _feature_properties(business):
    # Public fields only: this goes straight to the browser.
    return {
        "id": str(business.pk),
        "slug": business.slug,
        "name": business.name,
        "category": business.category.name,
        "rating_avg": business.rating_avg,
        "offers_delivery": business.offers_delivery,
    }


@require_safe
def businesses_geojson(request):
    bbox_form, filters = BBoxForm(request.GET), BusinessFilterForm(request.GET)
    # `&`, not `and`: validate both forms so all errors are reported.
    if not (bbox_form.is_valid() & filters.is_valid()):
        return JsonResponse({"errors": {**bbox_form.errors, **filters.errors}}, status=400)
    businesses = in_bbox(Business.objects.approved().select_related("category"), bbox_form.cleaned_data["bbox"])
    if category := filters.cleaned_data["category"]:
        businesses = businesses.filter(category=category)
    if filters.terms:
        # Not index-backed ($setIntersection), but bounded by the bbox and cap.
        businesses = businesses.filter(search_terms__contains=filters.terms)
    return JsonResponse(feature_collection(businesses[:MAX_MAP_FEATURES], _feature_properties))


@require_safe
def businesses_nearby(request):
    location, filters = NearbyQueryForm(request.GET), BusinessFilterForm(request.GET)
    if not (location.is_valid() & filters.is_valid()):
        context = {"location_error": bool(location.errors), "filter_error": bool(filters.errors)}
        return render(request, "directory/_nearby_list.html", context, status=400)

    # Raw MongoDB filter: built only from validated values and stored column names.
    query = {"status": Business.Status.APPROVED}
    if category := filters.cleaned_data["category"]:
        query["category_id"] = category.pk
    if filters.terms:
        query["search_terms"] = {"$all": filters.terms}
    businesses = list(
        nearest(Business, location.point, location.cleaned_data["radius_km"], MAX_NEARBY_RESULTS, query=query)
    )
    # raw_aggregate doesn't support select_related: resolve categories in one query.
    categories = Category.objects.in_bulk({b.category_id for b in businesses})
    for business in businesses:
        business.category = categories[business.category_id]
        business.distance_km = business.distance_m / 1000
    return render(
        request,
        "directory/_nearby_list.html",
        {
            "businesses": businesses,
            "radius_km": location.cleaned_data["radius_km"],
            "q": filters.cleaned_data["q"].strip(),
        },
    )


def get_visible_business(request, slug):
    """Approved businesses for everyone; any status for the owner and staff. Otherwise 404."""
    business = get_object_or_404(Business.objects.select_related("category"), slug=slug)
    is_owner = business.owner_id == request.user.pk
    if business.status != Business.Status.APPROVED and not (is_owner or request.user.is_staff):
        raise Http404
    business.viewer_is_owner = is_owner
    return business


MAX_LISTED_REVIEWS = 20


def _render_detail(request, business, review_form=None, edit_form=None, status=200):
    own_review = None
    if request.user.is_authenticated:
        own_review = Review.objects.filter(business=business, author=request.user).first()
    can_review = (
        request.user.is_authenticated
        and not business.viewer_is_owner
        and business.status == Business.Status.APPROVED
        and own_review is None
    )
    context = {
        "business": business,
        "reviews": business.reviews.filter(is_hidden=False).select_related("author")[:MAX_LISTED_REVIEWS],
        "own_review": own_review,
        "can_review": can_review,
        "review_form": review_form or (ReviewForm() if can_review else None),
        "edit_form": edit_form or (ReviewForm(instance=own_review) if own_review else None),
    }
    return render(request, "directory/detail.html", context, status=status)


@require_safe
def business_detail(request, slug):
    return _render_detail(request, get_visible_business(request, slug))


@require_safe
def business_panel(request, slug):
    return render(
        request, "directory/_detail_body.html", {"business": get_visible_business(request, slug), "in_panel": True}
    )


@login_required
@require_safe
def my_businesses(request):
    businesses = request.user.businesses.select_related("category").order_by("-created_at")
    return render(request, "directory/my_businesses.html", {"businesses": businesses})


@login_required
@require_http_methods(["GET", "HEAD", "POST"])
def business_create(request):
    return _edit_business(request, Business(owner=request.user))


@login_required
@require_http_methods(["GET", "HEAD", "POST"])
def business_edit(request, slug):
    # Scoped to the owner, so another user's listing is a 404 (no existence leak).
    return _edit_business(request, get_object_or_404(Business, slug=slug, owner=request.user))


def _edit_business(request, business):
    is_new = business._state.adding
    if request.method == "POST":
        form = BusinessForm(request.POST, instance=business)
        offerings = OfferingFormSet(request.POST, prefix="offerings")
        # `&`, not `and`: validate both so all errors show at once.
        if form.is_valid() & offerings.is_valid():
            business = form.save(commit=False)
            business.offerings = offerings.offerings()
            # Approved edits stay live (product.md open question); rejected ones go back to moderation.
            if business.status == Business.Status.REJECTED:
                business.status = Business.Status.PENDING
            business.save()
            if business.status == Business.Status.PENDING:
                message = _("“%(name)s” was submitted for review.")
            else:
                message = _("“%(name)s” was updated.")
            messages.success(request, message % {"name": business.name})
            return redirect("directory:my_businesses")
    else:
        form = BusinessForm(instance=business)
        offerings = OfferingFormSet(
            prefix="offerings",
            initial=[
                {"name": o.name, "price_from": o.price_from, "price_note": o.price_note, "description": o.description}
                for o in business.offerings
            ],
        )
    return render(
        request,
        "directory/business_form.html",
        {
            "form": form,
            "offerings": offerings,
            "business": business,
            "is_new": is_new,
            "tile_url": settings.MAP_TILE_URL,
            "default_center": settings.MAP_DEFAULT_CENTER,
        },
    )


def _reviewable_business(request, slug):
    """Approved business the current user may review: 404 otherwise, 403 for its owner."""
    business = get_object_or_404(Business.objects.approved().select_related("category"), slug=slug)
    business.viewer_is_owner = business.owner_id == request.user.pk
    if business.viewer_is_owner:
        raise PermissionDenied
    return business


@login_required
@require_POST
def review_create(request, slug):
    business = _reviewable_business(request, slug)
    form = ReviewForm(request.POST, instance=Review(business=business, author=request.user))
    if Review.objects.filter(business=business, author=request.user).exists():
        form.add_error(None, _("You already reviewed this business."))
    elif form.is_valid():
        try:
            with atomic():
                review = form.save()
                apply_rating_delta(business.pk, review.rating, 1)
        except IntegrityError:
            # Lost a race with a concurrent submit; the unique index held.
            form.add_error(None, _("You already reviewed this business."))
        else:
            messages.success(request, _("Thanks! Your review is posted."))
            return redirect("directory:detail", slug=business.slug)
    return _render_detail(request, business, review_form=form, status=400)


@login_required
@require_POST
def review_update(request, slug):
    business = _reviewable_business(request, slug)
    # Read the old rating in the same transaction as the write, so a concurrent hide can't skew the delta.
    with atomic():
        review = get_object_or_404(Review, business=business, author=request.user)
        old_rating = review.rating
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            review = form.save()
            if not review.is_hidden:
                apply_rating_delta(business.pk, review.rating - old_rating, 0)
    if not form.is_valid():
        return _render_detail(request, business, edit_form=form, status=400)
    messages.success(request, _("Your review was updated."))
    return redirect("directory:detail", slug=business.slug)


@login_required
@require_POST
def review_delete(request, slug):
    business = _reviewable_business(request, slug)
    review = get_object_or_404(Review, business=business, author=request.user)
    with atomic():
        review.delete()  # The post_delete signal adjusts the aggregate.
    messages.success(request, _("Your review was deleted."))
    return redirect("directory:detail", slug=business.slug)
