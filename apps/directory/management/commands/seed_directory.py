from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from apps.directory.models import Business, Category, Offering

SEED_EMAIL = "seed@example.invalid"

# (slug, name)
CATEGORIES = [
    ("bakery", "Bakery"),
    ("printing-apparel", "Printing & Apparel"),
    ("music-lessons", "Music Lessons"),
    ("food-truck", "Food Truck"),
    ("beauty", "Beauty"),
    ("home-services", "Home Services"),
    ("tutoring", "Tutoring"),
]


def offer(name, price=None, note="", description=""):
    return Offering(
        name=name, price_from=Decimal(price) if price else None, price_note=note, description=description
    )


# Fictional demo businesses, all inside the Doral bbox (-80.40,25.78,-80.30,25.86).
# Phone numbers use the reserved 555-01xx range; handles are obviously fake.
BUSINESSES = [
    {
        "slug": "la-casa-del-golfeado",
        "name": "La Casa del Golfeado",
        "category": "bakery",
        "lng": -80.3553, "lat": 25.8195,
        "description": "Family bakery making Venezuelan breads every morning. Party orders with 48 hours’ notice.",
        "started_on": date(2019, 5, 1),
        "offers_delivery": True,
        "instagram": "example_bakery",
        "phone": "(305) 555-0101",
        "offerings": [
            offer("Golfeados", "2.50", "each", "Sweet anise rolls with papelón and queso"),
            offer("Cachitos de jamón", "3.00", "each", "Ham-filled croissant rolls"),
            offer("Pan de jamón", "18.00", "per loaf", "Seasonal, December only"),
            offer("Party trays", description="Mixed pastries for events"),
        ],
    },
    {
        "slug": "panaderia-las-delicias",
        "name": "Panadería Las Delicias",
        "category": "bakery",
        "lng": -80.3480, "lat": 25.8105,
        "description": "Neighborhood bakery with fresh bread, pastries and coffee.",
        "started_on": date(2015, 9, 15),
        "offerings": [
            offer("Golfeados con queso", "3.00", "each"),
            offer("Tequeños", "1.50", "each", "Cheese sticks, frozen packs available"),
            offer("Café con leche", "2.75"),
        ],
    },
    {
        "slug": "doral-print-lab",
        "name": "Doral Print Lab",
        "category": "printing-apparel",
        "lng": -80.3400, "lat": 25.8000,
        "description": "Custom t-shirts, uniforms and banners. Small runs welcome.",
        "started_on": date(2020, 2, 1),
        "offers_delivery": True,
        "website": "https://example.com/print-lab",
        "offerings": [
            offer("T-shirt printing", "12.00", "per shirt", "Screen print or DTF, minimum 6"),
            offer("Embroidery", "15.00", "per piece", "Logos on polos and caps"),
            offer("Vinyl banners", "45.00", "per banner"),
        ],
    },
    {
        "slug": "andres-guitar-lessons",
        "name": "Andrés Guitar Lessons",
        "category": "music-lessons",
        "lng": -80.3700, "lat": 25.8300,
        "description": "Guitar and cuatro lessons for kids and adults, in Spanish or English.",
        "started_on": date(2018, 3, 1),
        "instagram": "example_guitar",
        "offerings": [
            offer("Guitar lessons", "35.00", "per hour", "Acoustic or electric, all ages"),
            offer("Cuatro lessons", "35.00", "per hour", "Venezuelan cuatro, beginners welcome"),
            offer("Group class for kids", description="Saturdays, small groups"),
        ],
    },
    {
        "slug": "sabor-caraqueno-food-truck",
        "name": "Sabor Caraqueño Food Truck",
        "category": "food-truck",
        "lng": -80.3620, "lat": 25.7990,
        "description": "Arepas and Venezuelan street food. Weekends near the park.",
        "started_on": date(2022, 6, 10),
        "offers_delivery": True,
        "instagram": "example_foodtruck",
        "offerings": [
            offer("Arepas", "8.00", "each", "Reina pepiada, pabellón, dominó"),
            offer("Golfeados (weekends)", description="While they last"),
            offer("Cachapas", "10.00", "each"),
        ],
    },
    {
        "slug": "glow-nails-doral",
        "name": "Glow Nails Doral",
        "category": "beauty",
        "lng": -80.3350, "lat": 25.8250,
        "description": "Manicures, pedicures and nail art by appointment.",
        "started_on": date(2021, 11, 20),
        "phone": "(305) 555-0106",
        "offerings": [
            offer("Manicure", "25.00"),
            offer("Pedicure", "35.00"),
            offer("Nail art", "10.00", "add-on"),
        ],
    },
    {
        "slug": "fixit-doral-handyman",
        "name": "FixIt Doral Handyman",
        "category": "home-services",
        "lng": -80.3800, "lat": 25.8150,
        "description": "Small repairs, furniture assembly and TV mounting.",
        "started_on": date(2017, 1, 5),
        "phone": "(305) 555-0107",
        "offerings": [
            offer("Handyman service", "60.00", "per hour"),
            offer("TV mounting", "90.00", "per TV"),
            offer("Furniture assembly", "50.00", "per item"),
        ],
    },
    {
        "slug": "doral-math-tutoring",
        "name": "Doral Math Tutoring",
        "category": "tutoring",
        "lng": -80.3900, "lat": 25.8400,
        "description": "Math and SAT prep for middle and high school students.",
        "started_on": date(2025, 9, 1),
        "offerings": [
            offer("Math tutoring", "30.00", "per hour", "Algebra, geometry, calculus"),
            offer("SAT prep", "40.00", "per hour"),
        ],
    },
]


class Command(BaseCommand):
    help = "Load fictional Doral, FL demo businesses (idempotent: existing slugs are skipped)."

    def handle(self, *args, **options):
        owner, created = get_user_model().objects.get_or_create(email=SEED_EMAIL, defaults={"first_name": "Demo"})
        if created:
            owner.set_unusable_password()
            owner.save(update_fields=["password"])

        categories = {}
        for slug, name in CATEGORIES:
            categories[slug], _ = Category.objects.get_or_create(slug=slug, defaults={"name": name})

        existing = set(Business.objects.filter(slug__in=[b["slug"] for b in BUSINESSES]).values_list("slug", flat=True))
        created_count = 0
        for data in BUSINESSES:
            if data["slug"] in existing:
                continue
            fields = {k: v for k, v in data.items() if k not in ("category", "lng", "lat")}
            Business.objects.create(
                owner=owner,
                category=categories[data["category"]],
                location=Point(data["lng"], data["lat"], srid=4326),
                status=Business.Status.APPROVED,
                **fields,
            )
            created_count += 1
        self.stdout.write(self.style.SUCCESS(f"Created {created_count} businesses ({len(existing)} already present)."))
