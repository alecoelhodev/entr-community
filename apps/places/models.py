from django.contrib.gis.db import models
from django_mongodb_backend.managers import MongoManager


class Place(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    # Stored as GeoJSON; the backend creates a 2dsphere index automatically.
    location = models.PointField(srid=4326)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = MongoManager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
