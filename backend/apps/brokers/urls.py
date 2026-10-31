from django.urls import path

from . import views

urlpatterns = [
    path("me/", views.BrokerMeView.as_view(), name="broker-me"),
    path("<int:pk>/", views.BrokerDetailView.as_view(), name="broker-detail"),
    path("agency/", views.AgencyMeView.as_view(), name="agency-me"),
    path("agency/members/", views.AgencyMembersView.as_view(), name="agency-members"),
    path(
        "agency/members/<int:pk>/",
        views.AgencyMemberDetailView.as_view(),
        name="agency-member-detail",
    ),
    path("agencies/<int:pk>/", views.AgencyDetailView.as_view(), name="agency-detail"),
]
