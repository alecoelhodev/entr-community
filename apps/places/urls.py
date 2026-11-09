from django.urls import path

from . import views

app_name = "places"

urlpatterns = [
    path("", views.map_page, name="map"),
    path("places.geojson", views.places_geojson, name="geojson"),
    path("places/nearby/", views.places_nearby, name="nearby"),
]
