from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe

from apps.geo.forms import BBoxForm, NearbyQueryForm
from apps.geo.geojson import feature_collection
from apps.geo.queries import in_bbox, nearest

from .forms import BusinessFilterForm
from .models import Business, Category

MAX_MAP_FEATURES = 500
MAX_NEARBY_RESULTS = 50


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
        {"businesses": businesses, "radius_km": location.cleaned_data["radius_km"]},
    )
