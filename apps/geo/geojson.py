def feature_collection(objects, properties, field: str = "location") -> dict:
    """Serialize objects with a point field to a GeoJSON FeatureCollection.

    `properties` maps an object to its feature's properties dict; keep it to
    public fields only, since the output goes straight to the browser.
    """
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": list(getattr(obj, field).coords)},
                "properties": properties(obj),
            }
            for obj in objects
        ],
    }
