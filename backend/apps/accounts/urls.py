from django.urls import path

from .views import MeView, NafathStartView, NafathStatusView

urlpatterns = [
    path("me/", MeView.as_view(), name="accounts-me"),
    path("nafath/start/", NafathStartView.as_view(), name="nafath-start"),
    path("nafath/status/", NafathStatusView.as_view(), name="nafath-status"),
]
