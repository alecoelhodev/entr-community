from django.urls import path

from . import views

app_name = "directory"

urlpatterns = [
    path("", views.map_page, name="map"),
    path("businesses.geojson", views.businesses_geojson, name="geojson"),
    path("businesses/nearby/", views.businesses_nearby, name="nearby"),
    path("b/<slug:slug>/", views.business_detail, name="detail"),
    path("b/<slug:slug>/panel/", views.business_panel, name="panel"),
    path("b/<slug:slug>/reviews/", views.review_create, name="review_create"),
    path("b/<slug:slug>/reviews/mine/", views.review_update, name="review_update"),
    path("b/<slug:slug>/reviews/mine/delete/", views.review_delete, name="review_delete"),
    path("me/businesses/", views.my_businesses, name="my_businesses"),
    path("me/businesses/new/", views.business_create, name="business_create"),
    path("me/businesses/<slug:slug>/edit/", views.business_edit, name="business_edit"),
]
