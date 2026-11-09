from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe

from apps.geo.forms import BBoxForm, NearbyQueryForm
from apps.geo.geojson import feature_collection
from apps.geo.queries import in_bbox, nearest

from .models import Place

MAX_MAP_FEATURES = 500
MAX_NEARBY_RESULTS = 50


@require_safe
def map_page(request):
    return render(request, "places/map.html", {"tile_url": settings.MAP_TILE_URL})


@require_safe
def places_geojson(request):
    form = BBoxForm(request.GET)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)
    places = in_bbox(Place.objects.all(), form.cleaned_data["bbox"])[:MAX_MAP_FEATURES]
    return JsonResponse(feature_collection(places, lambda p: {"id": str(p.pk), "name": p.name}))


@require_safe
def places_nearby(request):
    form = NearbyQueryForm(request.GET)
    if not form.is_valid():
        return render(request, "places/_nearby_list.html", {"form": form}, status=400)
    places = nearest(Place, form.point, form.cleaned_data["radius_km"], MAX_NEARBY_RESULTS)
    return render(
        request,
        "places/_nearby_list.html",
        {"form": form, "places": places, "radius_km": form.cleaned_data["radius_km"]},
    )
