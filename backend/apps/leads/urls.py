from django.urls import path

from . import views

urlpatterns = [
    path("", views.CreateLeadView.as_view(), name="lead-create"),
]
