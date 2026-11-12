from django.urls import path

from .views import AreaCountsView, SitemapListingsView

urlpatterns = [
    path("areas/", AreaCountsView.as_view(), name="seo-areas"),
    path("sitemap/listings/", SitemapListingsView.as_view(), name="seo-sitemap-listings"),
]
