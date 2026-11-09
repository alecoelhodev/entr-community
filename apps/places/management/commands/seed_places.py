from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from apps.places.models import Place

# (name, lng, lat) — a few Lisbon landmarks for local development.
SAMPLE_PLACES = [
    ("Praça do Comércio", -9.1366, 38.7076),
    ("Castelo de São Jorge", -9.1335, 38.7139),
    ("Miradouro da Senhora do Monte", -9.1327, 38.7190),
    ("LX Factory", -9.1784, 38.7037),
    ("Torre de Belém", -9.2160, 38.6916),
    ("Parque Eduardo VII", -9.1540, 38.7287),
    ("Oceanário de Lisboa", -9.0937, 38.7635),
]


class Command(BaseCommand):
    help = "Insert sample places (skips names that already exist)."

    def handle(self, *args, **options):
        existing = set(Place.objects.values_list("name", flat=True))
        new = [
            Place(name=name, location=Point(lng, lat, srid=4326))
            for name, lng, lat in SAMPLE_PLACES
            if name not in existing
        ]
        Place.objects.bulk_create(new)
        self.stdout.write(self.style.SUCCESS(f"Created {len(new)} places."))
