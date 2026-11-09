# entr community

Django 6.1 + HTMX + Alpine.js (CSP build) + MongoDB 8 (official `django-mongodb-backend` with GeoDjango) + Leaflet/OpenStreetMap.

## Run

```sh
docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_places      # Lisbon sample data
docker compose exec web python manage.py createsuperuser
```

Open http://localhost:8000 (map) and http://localhost:8000/admin/.

```sh
docker compose exec web python manage.py test
```

## Geo foundation

- Spatial fields (`PointField`, `PolygonField`, …) are stored as GeoJSON with an automatic `2dsphere` index. SRID 4326 only.
- ORM lookups: `within`, `intersects`, `contains`, `disjoint`, `distance_lte/gt` (accepts `D(km=…)`), `dwithin` (degrees only).
- No GIS DB functions (e.g. `Distance()`); for distance-sorted results use `apps.geo.queries.nearest` (`$geoNear` via `raw_aggregate`, needs `objects = MongoManager()`).
- Validate request coordinates with `apps.geo.forms`. Coordinate order: GEOS/GeoJSON `(lng, lat)`, Leaflet `[lat, lng]`.

## Notes

- New contrib/third-party apps with models need ObjectId-based AppConfigs (`config/apps.py`) and migrations in `mongo_migrations/` (`makemigrations <app>`).
- Front-end libs are vendored in `static/vendor/` (versions in `static/vendor/VERSIONS`). Alpine is the CSP build: register components with `Alpine.data()` in JS; no inline expressions beyond simple property access.
- The public OSM tile server is for light use only. Set `MAP_TILE_URL` to a commercial or self-hosted tile server before production traffic (the CSP `img-src` follows it).
- Production: set `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `MONGODB_URI`; the image runs gunicorn by default. See `.env.example`.
