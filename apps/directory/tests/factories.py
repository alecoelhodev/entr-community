from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point

from apps.directory.models import Business, Category, Offering

DORAL_BBOX = "-80.40,25.78,-80.30,25.86"
BAKERY_POINT = Point(-80.3553, 25.8195, srid=4326)


def directory_fixture(test_cls):
    """Doral businesses shared by the API and page tests; set as class attributes."""
    owner = get_user_model().objects.create_user(email="owner@example.com", password="x")
    bakery = Category.objects.create(name="Bakery", slug="bakery")
    printing = Category.objects.create(name="Printing & Apparel", slug="printing-apparel")
    music = Category.objects.create(name="Music Lessons", slug="music-lessons")
    approved = Business.Status.APPROVED

    test_cls.owner = owner
    test_cls.categories = {"bakery": bakery, "printing": printing, "music": music}
    test_cls.bakery = Business.objects.create(
        owner=owner, category=bakery, name="La Casa del Golfeado", status=approved,
        location=BAKERY_POINT, rating_sum=14, rating_count=3,
        offerings=[
            Offering(name="Golfeados", price_from=Decimal("2.50"), price_note="each"),
            Offering(name="Cachitos", price_from=Decimal("2.75")),
        ],
    )
    test_cls.print_shop = Business.objects.create(
        owner=owner, category=printing, name="Doral Print Lab", status=approved,
        location=Point(-80.3400, 25.8000, srid=4326), offers_delivery=True,
        offerings=[Offering(name="T-shirt printing", price_from=Decimal("12"))],
    )
    test_cls.guitar = Business.objects.create(
        owner=owner, category=music, name="Profe Luis Guitar", status=approved,
        location=Point(-80.3700, 25.8300, srid=4326),
        offerings=[Offering(name="Guitar lessons", price_note="per hour")],
    )
    test_cls.pending_bakery = Business.objects.create(
        owner=owner, category=bakery, name="Pending Panadería",
        location=Point(-80.3560, 25.8200, srid=4326), offerings=[Offering(name="Golfeados")],
    )
    test_cls.orlando_bakery = Business.objects.create(
        owner=owner, category=bakery, name="Orlando Golfeados", status=approved,
        location=Point(-81.3792, 28.5383, srid=4326), offerings=[Offering(name="Golfeados")],
    )
