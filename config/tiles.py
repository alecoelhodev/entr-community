from urllib.parse import urlsplit

_OSM = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
_MAPTILER = '<a href="https://www.maptiler.com/copyright/">&copy; MapTiler</a> ' + (
    '<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>'
)
_ATTRIBUTIONS = {"api.maptiler.com": _MAPTILER}


def tile_config(url):
    """Return (CSP origin, attribution HTML) for a tile URL template; `{s}.` becomes a `*.` wildcard."""
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}".replace("{s}.", "*.")
    return origin, _ATTRIBUTIONS.get(parts.hostname, _OSM)
