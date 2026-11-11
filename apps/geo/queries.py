"""Reusable geospatial query helpers for MongoDB-backed GeoDjango models.

The backend supports the `within`, `intersects`, `contains`, `disjoint`,
`dwithin` and `distance_lte/gt` lookups. Anything else (e.g. results sorted by
distance) goes through `raw_aggregate()` with MongoDB's own operators.
"""

from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.measure import D


def near(queryset, point: Point, radius_km: float, field: str = "location"):
    """Objects within `radius_km` of `point` (unordered)."""
    return queryset.filter(**{f"{field}__distance_lte": (point, D(km=radius_km))})


def in_bbox(queryset, bbox: Polygon, field: str = "location"):
    return queryset.filter(**{f"{field}__within": bbox})


def nearest(
    model, point: Point, radius_km: float, limit: int, field: str = "location", query: dict | None = None
):
    """Objects within `radius_km`, closest first, each annotated with `distance_m`.

    `query` is a raw MongoDB filter applied inside `$geoNear` (so it runs
    before the limit and can use indexes). It uses stored column names, e.g.
    `category_id` for a FK. Build it only from validated values, never from
    raw request strings.

    Requires the model's manager to be a `MongoManager` and `field` to have a
    2dsphere index (the backend creates one for every spatial field).
    """
    geo_near = {
        "near": {"type": "Point", "coordinates": [point.x, point.y]},
        "key": field,
        "distanceField": "distance_m",
        "maxDistance": radius_km * 1000,
        "spherical": True,
    }
    if query:
        geo_near["query"] = query
    return model.objects.raw_aggregate([{"$geoNear": geo_near}, {"$limit": limit}])
