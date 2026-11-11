from django.urls import path

from . import views

app_name = "directory"

urlpatterns = [
    path("businesses.geojson", views.businesses_geojson, name="geojson"),
    path("businesses/nearby/", views.businesses_nearby, name="nearby"),
]
