from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_safe

from apps.geo.forms import BBoxForm, NearbyQueryForm
from apps.geo.geojson import feature_collection
from apps.geo.queries import in_bbox, nearest

from .forms import BusinessFilterForm, BusinessForm, OfferingFormSet
from .models import Business, Category

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


@require_safe
def business_detail(request, slug):
    return render(request, "directory/detail.html", {"business": get_visible_business(request, slug)})


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
