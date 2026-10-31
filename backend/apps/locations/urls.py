from django.urls import path

from .views import CityListView, DistrictListView

urlpatterns = [
    path("cities/", CityListView.as_view(), name="locations-cities"),
    path(
        "cities/<slug:city_slug>/districts/",
        DistrictListView.as_view(),
        name="locations-districts",
    ),
]
