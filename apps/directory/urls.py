from django.urls import path

from . import views

app_name = "directory"

urlpatterns = [
    path("businesses.geojson", views.businesses_geojson, name="geojson"),
    path("businesses/nearby/", views.businesses_nearby, name="nearby"),
    path("b/<slug:slug>/", views.business_detail, name="detail"),
    path("b/<slug:slug>/panel/", views.business_panel, name="panel"),
    path("me/businesses/", views.my_businesses, name="my_businesses"),
    path("me/businesses/new/", views.business_create, name="business_create"),
    path("me/businesses/<slug:slug>/edit/", views.business_edit, name="business_edit"),
]
